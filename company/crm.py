"""CRM primitives: company leads, deduplication, scoring, proposals and suppression."""
from __future__ import annotations
import re, uuid
from urllib.parse import urlparse
from datetime import datetime, timezone
from .store import TaskStore

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
UNSUBSCRIBE_RE = re.compile(r"unsubscribe|opt[ -]?out|remove me|stop emailing|iletişimden çık|iletisimden cik|abonelikten çık|abonelikten cik", re.I)
SENSITIVE_MAIL_RE = re.compile(r"refund|iade|chargeback|dispute|itiraz|invoice|fatura|legal|avukat|kvkk|gdpr|delete my data|verilerimi sil|security|güvenlik|guvenlik|breach|complaint|şikayet|sikayet", re.I)

def now():
    return datetime.now(timezone.utc).isoformat()

def norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold().translate(str.maketrans({"ı":"i","ş":"s","ğ":"g","ü":"u","ö":"o","ç":"c"}))).strip()

def norm_email(value: str) -> str:
    return value.strip().casefold()

def _db(store=None):
    return store or TaskStore()

def score_company(data: dict) -> dict:
    # Evidence-based fit score: only explicitly supplied signals receive points.
    signals = {
        "need_fit": 25 if data.get("need_summary") else 0,
        "industry_fit": 15 if data.get("industry") else 0,
        "source_quality": 15 if data.get("source_url") and data.get("source_name")
            and data.get("source_validation_status") in ("reachable_match", "reachable_unparsed")
            and data.get("source_type") == "human_verified" else 0,
        "contactability": 15 if data.get("public_contact_channel") or data.get("business_email") else 0,
        "website": 10 if data.get("website") else 0,
        "country_fit": 10 if data.get("country") and data.get("country") != "Unknown" else 0,
        "evidence_rationale": 10 if data.get("fit_reason") else 0,
    }
    total = sum(signals.values())
    return {"score": total, "breakdown": signals}

def upsert_company(data: dict, store=None) -> dict:
    db = _db(store)
    name = " ".join(data["company_name"].split())
    country = (data.get("country") or "Unknown").strip()
    source_url = str(data.get("source_url") or "").strip()
    if urlparse(source_url).scheme != "https" or not urlparse(source_url).netloc:
        raise ValueError("A public HTTPS source URL is required")
    normalized = norm_name(name)
    website = (data.get("website") or "").strip().rstrip("/").lower() or None
    score = score_company(data)
    existing = db._request("crm_companies", params={
        "select":"*", "normalized_name":f"eq.{normalized}", "country":f"eq.{country}", "limit":"1"
    })
    if not existing and website:
        existing = db._request("crm_companies", params={
            "select":"*", "website":f"eq.{website}", "limit":"1"
        })
    company_id = existing[0]["company_id"] if existing else "co-" + uuid.uuid4().hex[:12]
    row = {
        "company_id":company_id, "company_name":name, "normalized_name":normalized,
        "country":country, "website":website, "industry":data.get("industry"),
        "company_size":data.get("company_size"), "source_name":data.get("source_name") or "unknown",
        "source_url":source_url,
        "source_type":data.get("source_type") or "public_web",
        "source_validation_status":data.get("source_validation_status") or "not_checked",
        "source_http_status":data.get("source_http_status"),
        "source_page_title":data.get("source_page_title"),
        "source_checked_at":data.get("source_checked_at"),
        "source_validation_note":data.get("source_validation_note"),
        "public_contact_channel":data.get("public_contact_channel"),
        "business_email":norm_email(data["business_email"]) if data.get("business_email") else None,
        "need_summary":data.get("need_summary"), "fit_reason":data.get("fit_reason"),
        "score":score["score"], "score_breakdown":score["breakdown"],
        "last_researched_at":now(), "updated_at":now()
    }
    db._request("crm_companies","POST",{"on_conflict":"normalized_name,country"},row,
                "resolution=merge-duplicates,return=representation")
    rows=db._request("crm_companies",params={"select":"*","company_id":f"eq.{company_id}","limit":"1"})
    return rows[0] if rows else row


def verify_company(company_id: str, store=None) -> dict:
    """Human-confirm a source already checked as reachable; AI reachability alone is not enough."""
    db = _db(store)
    rows = db._request("crm_companies", params={
        "select": "*", "company_id": f"eq.{company_id}", "limit": "1"
    })
    if not rows:
        raise KeyError("Company not found")
    company = rows[0]
    if company.get("source_validation_status") not in ("reachable_match", "reachable_unparsed"):
        raise ValueError("Company source must be reachable and eligible for manual review first")
    verified = {**company, "source_type": "human_verified"}
    score = score_company(verified)
    db._request("crm_companies", "PATCH", {"company_id": f"eq.{company_id}"}, {
        "source_type": "human_verified", "score": score["score"],
        "score_breakdown": score["breakdown"], "updated_at": now(),
    }, "return=minimal")
    rows = db._request("crm_companies", params={
        "select": "*", "company_id": f"eq.{company_id}", "limit": "1"
    })
    return rows[0] if rows else verified

def list_companies(store=None, limit=100, query="", stage=None):
    params={"select":"*","order":"score.desc,updated_at.desc","limit":str(max(1,min(limit,250)))}
    if stage: params["stage"]=f"eq.{stage}"
    if query:
        # Never interpolate PostgREST grammar characters from user input.
        safe = re.sub(r"[^0-9a-zA-ZğüşöçıİĞÜŞÖÇ _-]", "", query)[:80].strip()
        if safe:
            params["or"] = f"(company_name.ilike.*{safe}*,country.ilike.*{safe}*,industry.ilike.*{safe}*)"
    return _db(store)._request("crm_companies",params=params)

def upsert_contact(company_id: str | None, data: dict, store=None) -> dict:
    db=_db(store)
    email=norm_email(data["email"])
    if not EMAIL_RE.match(email): raise ValueError("Invalid business email")
    source_url = str(data.get("source_url") or "").strip()
    if urlparse(source_url).scheme != "https" or not urlparse(source_url).netloc:
        raise ValueError("A public HTTPS source URL is required")
    existing=db._request("crm_contacts",params={"select":"*","normalized_email":f"eq.{email}","limit":"1"})
    contact_id=existing[0]["contact_id"] if existing else "ct-"+uuid.uuid4().hex[:12]
    row={"contact_id":contact_id,"company_id":company_id,"full_name":data.get("full_name"),
         "role":data.get("role"),"email":email,"normalized_email":email,
         "source_name":data.get("source_name") or "unknown","source_url":source_url,
         "legal_basis":data.get("legal_basis") or "unverified",
         "consent_status":data.get("consent_status") or "unknown",
         "updated_at":now()}
    db._request("crm_contacts","POST",{"on_conflict":"normalized_email"},row,
                "resolution=merge-duplicates,return=minimal")
    rows=db._request("crm_contacts",params={"select":"*","contact_id":f"eq.{contact_id}","limit":"1"})
    return rows[0] if rows else row

def suppress_contact(email: str, reason: str, source="manual", store=None):
    db=_db(store); normalized=norm_email(email)
    if not EMAIL_RE.match(normalized): raise ValueError("Invalid email")
    db._request("crm_suppressions","POST",{"on_conflict":"normalized_email"},
        {"suppression_id":"sp-"+uuid.uuid4().hex[:12],"normalized_email":normalized,
         "reason":reason[:300],"source":source,"created_at":now()},
        "resolution=ignore-duplicates,return=minimal")
    db._request("crm_contacts","PATCH",{"normalized_email":f"eq.{normalized}"},
        {"do_not_contact":True,"consent_status":"withdrawn","unsubscribed_at":now(),"updated_at":now()},
        "return=minimal")
    db._request("crm_mail_log","PATCH",{"normalized_email":f"eq.{normalized}"},
        {"do_not_contact":True},"return=minimal")
    return {"email":normalized,"suppressed":True}

def is_suppressed(email: str, store=None) -> bool:
    normalized=norm_email(email)
    if not normalized: return True
    db=_db(store)
    rows=db._request("crm_suppressions",params={"select":"suppression_id","normalized_email":f"eq.{normalized}","limit":"1"})
    if rows: return True
    rows=db._request("crm_contacts",params={"select":"contact_id","normalized_email":f"eq.{normalized}","do_not_contact":"eq.true","limit":"1"})
    return bool(rows)

def record_mail(email: str, direction: str, subject: str, body: str, external_id="", thread_id="", store=None):
    db=_db(store); normalized=norm_email(email)
    unsub=bool(UNSUBSCRIBE_RE.search((subject or "")+" "+(body or "")))
    if unsub and direction=="inbound":
        suppress_contact(normalized,"Unsubscribe request in inbound email","inbound_email",db)
    sensitive=bool(SENSITIVE_MAIL_RE.search((subject or "")+" "+(body or "")))
    category="unsubscribe" if unsub else "sensitive_escalation" if sensitive else "sales_inquiry" if direction=="inbound" else "outbound"
    suppressed=is_suppressed(normalized,db)
    row={"mail_id":"ml-"+uuid.uuid4().hex[:12],"external_message_id":external_id or None,
         "thread_id":thread_id or None,"contact_email":normalized,"normalized_email":normalized,
         "direction":direction,"category":category,"sentiment":"unknown","subject":(subject or "")[:200],
         "snippet":(body or "")[:500],"action_required":sensitive or unsub,
         "do_not_contact":suppressed,"created_at":now()}
    db._request("crm_mail_log","POST",body=row,prefer="return=minimal")
    return {"category":category,"action_required":sensitive or unsub,"do_not_contact":suppressed}

def create_offer(company_id: str, product_name: str, store=None) -> dict:
    db=_db(store)
    rows=db._request("crm_companies",params={"select":"*","company_id":f"eq.{company_id}","limit":"1"})
    if not rows: raise KeyError("Company not found")
    company=rows[0]
    if company.get("source_type") != "human_verified" or company.get("stage") not in {"qualified", "proposal", "negotiation"}:
        raise PermissionError("Only a human-verified, qualified company can receive a proposal draft")
    contact=db._request("crm_contacts",params={"select":"*","company_id":f"eq.{company_id}","limit":"1"})
    c=contact[0] if contact else None
    if c and is_suppressed(c["email"],db): raise PermissionError("Contact is suppressed; proposal email cannot be prepared")
    name=company["company_name"]; need=company.get("need_summary") or "network operations efficiency"
    subject=f"{product_name} | {name} için kısa değerlendirme"
    body=(f"Merhaba {c.get('full_name') if c else ''},\n\n"
          f"{name} için kamuya açık kaynaklarda görülen ihtiyaç ve notlarımızı inceledik: {need}. "
          f"{company.get('fit_reason') or 'Bu ihtiyaca uygun olabilecek yaklaşımı değerlendirmek isteriz.'}\n\n"
          f"{product_name}, ağ ekiplerinin çok üreticili operasyonlarını daha düzenli yürütmesine yardımcı olmayı hedefler. "
          "İhtiyacınızı ve mevcut sürecinizi 15 dakikalık kısa bir görüşmede anlamak isteriz. "
          "Bu mesaj bir ön taslaktır; kapsam, fiyat ve teslim koşulları ayrıca teyit edilmelidir.\n\n"
          "İlgilenmiyorsanız bu e-postayı yanıtlayarak iletişimden çıkabilirsiniz.")
    offer={"offer_id":"of-"+uuid.uuid4().hex[:12],"company_id":company_id,
           "contact_id":c["contact_id"] if c else None,"product_name":product_name,
           "currency":"USD","proposal_text":f"Problem: {need}\nYaklaşım: {product_name}\nDurum: ön teklif, insan incelemesi gerekli",
           "email_subject":subject,"email_body":body,"status":"draft","created_at":now(),"updated_at":now()}
    db._request("crm_offers","POST",body=offer,prefer="return=minimal")
    return offer

def list_followups(store=None):
    return _db(store)._request("crm_followups",params={"select":"*","status":"eq.pending","order":"due_at.asc","limit":"100"})


def list_contacts(company_id: str | None = None, store=None):
    params={"select":"*","order":"created_at.desc","limit":"200"}
    if company_id: params["company_id"]=f"eq.{company_id}"
    return _db(store)._request("crm_contacts",params=params)

def update_company_stage(company_id: str, stage: str, store=None):
    allowed={"new","qualified","proposal","negotiation","won","lost","nurture","suppressed"}
    if stage not in allowed: raise ValueError("Invalid CRM stage")
    db=_db(store)
    current = db._request("crm_companies", params={"select":"*","company_id":f"eq.{company_id}","limit":"1"})
    if not current: raise KeyError("Company not found")
    if stage in {"qualified", "proposal", "negotiation", "won"} and current[0].get("source_type") != "human_verified":
        raise PermissionError("Human verification is required before advancing a company to a sales stage")
    db._request("crm_companies","PATCH",{"company_id":f"eq.{company_id}"},
                {"stage":stage,"updated_at":now()},"return=minimal")
    rows=db._request("crm_companies",params={"select":"*","company_id":f"eq.{company_id}","limit":"1"})
    if not rows: raise KeyError("Company not found")
    return rows[0]
