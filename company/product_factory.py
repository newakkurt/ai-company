"""Bounded AI digital-product factory.

Generated code is treated as untrusted source: it is never imported or executed
by the factory. Packaging, syntax checks, policy scans and SHA-256 are local.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from uuid import uuid4

from .agents import load_agents
from .llm import get_provider
from .store import TaskStore

OUTPUT_ROOT = Path(os.getenv("AI_COMPANY_PRODUCT_DIR", "/tmp/ai-company-products"))
FACTORY_MAX_OUTPUT_TOKENS = 32000
MAX_FILES = 18
MAX_FILE_BYTES = 180_000
MAX_TOTAL_BYTES = 900_000
ALLOWED_SUFFIXES = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".html", ".css", ".js", ".ts", ".sql", ".cfg"}
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
RISK_PATTERNS = [
    re.compile(r"(?i)\b(eval|exec)\s*\("),
    re.compile(r"(?i)\b(subprocess|os\.system|pty\.)"),
    re.compile(r"(?i)\b(requests\.(?:get|post)|urlopen)\s*\("),
    re.compile(r"(?i)\b(socket|paramiko|netmiko)\b"),
]


def score_idea(idea: dict) -> dict:
    """Transparent 0-100 opportunity score; inputs are explicit 1..5 ratings."""
    weights = {
        "problem_urgency": 0.22,
        "willingness_to_pay": 0.20,
        "market_access": 0.15,
        "feasibility": 0.15,
        "differentiation": 0.12,
        "time_to_revenue": 0.10,
        "supportability": 0.06,
    }
    risk = int(idea.get("security_risk", 1))
    if not 1 <= risk <= 5:
        raise ValueError("security_risk must be between 1 and 5")
    values = {}
    for key in weights:
        value = int(idea.get(key, 3))
        if not 1 <= value <= 5:
            raise ValueError(f"{key} must be between 1 and 5")
        values[key] = value
    raw = sum(values[k] * w for k, w in weights.items()) / 5 * 100
    penalty = (risk - 1) * 4
    total = max(0, round(raw - penalty))
    return {
        "score": total,
        "risk_penalty": penalty,
        "weights": weights,
        "ratings": values,
        "security_risk": risk,
        "decision": "BUILD_CANDIDATE" if total >= 75 else "VALIDATE_MORE" if total >= 55 else "BACKLOG",
        "explanation": "Ağırlıklı puan; güvenlik riski için açık ceza uygulanır. Pazar verisi doğrulanmış sayılmaz.",
    }


def create_research_task(description: str, store=None) -> dict:
    store = store or TaskStore()
    task = store.create_task(
        "DIGITAL PRODUCT MARKET RESEARCH. " + description.strip()
        + "\nDeliver: cited demand evidence, recurring buyer pain, competing alternatives, "
          "buyer roles, willingness-to-pay signals, risk and one minimal product opportunity. "
          "Use public sources only; distinguish evidence from assumptions. Draft/analysis only; "
          "do not contact anyone, purchase, publish or execute code."
    )
    roles = ["ceo", "research_intelligence", "product_business", "marketing_growth",
             "technology_architect", "network_infrastructure", "security_compliance", "qa_testing"]
    known = {a.id for a in load_agents()}
    store.assign_agents(task["task_id"], [r for r in roles if r in known])
    return {"task_id": task["task_id"], "status": "planned", "agents": [r for r in roles if r in known]}


def _clean_files(raw: object) -> tuple[dict[str, str], list[str]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("Model did not return a non-empty files object")
    if len(raw) > MAX_FILES:
        raise ValueError(f"Too many generated files; maximum is {MAX_FILES}")
    cleaned: dict[str, str] = {}
    warnings: list[str] = []
    total = 0
    for name, content in raw.items():
        if not isinstance(name, str) or not isinstance(content, str):
            raise ValueError("Generated files must map string paths to string content")
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or "\\" in name
            or "\x00" in name
            or ":" in name
            or ".." in path.parts
            or not path.parts
            or path.suffix.lower() not in ALLOWED_SUFFIXES
        ):
            raise ValueError(f"Unsafe or unsupported generated path: {name!r}")
        if name in cleaned or len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError(f"Duplicate or oversized file: {name}")
        total += len(content.encode("utf-8"))
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Generated source exceeds total size limit")
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            raise ValueError(f"Possible hard-coded secret found in {name}; package rejected")
        if path.suffix == ".py":
            try:
                ast.parse(content, filename=name)
            except SyntaxError as exc:
                warnings.append(f"{name}: Python syntax error at line {exc.lineno}: {exc.msg}")
        for pattern in RISK_PATTERNS:
            if pattern.search(content):
                warnings.append(f"{name}: manual security review required ({pattern.pattern})")
        cleaned[name] = content
    return cleaned, warnings


def build_product(name: str, description: str, product_type: str = "python_api",
                  version: str = "0.1.0", provider=None) -> dict:
    """Generate a small source package and release evidence without executing its code."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{1,59}", name.strip()):
        raise ValueError("Product name must be 2-60 safe characters")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Version must use semantic version format, e.g. 0.1.0")
    if product_type not in {"python_api", "web_app", "python_cli"}:
        raise ValueError("Unsupported product_type")
    provider = provider or get_provider()
    prompt = f"""
Create a small, genuinely useful, self-contained MVP product package.
Product: {name}
Problem and target buyer: {description}
Target type: {product_type}; version: {version}
Return ONLY valid JSON with shape {{"summary":"...","files":{{"src/main.py":"...","README.md":"..."}},"sample_data":{{}},"test_plan":["..."]}}.
Requirements:
- Generate source, a runnable local demo, sample data and meaningful automated tests.
- For python_api use FastAPI; for web_app use static HTML/CSS/JS unless API is essential;
  for python_cli use standard-library Python by default.
- Include setup instructions, limitations, security notes and example usage in README.md.
- Include tests/ files where practical; do not claim tests were run.
- No secrets, telemetry, external network calls, shell execution, eval/exec, destructive actions,
  production device access or paid services. Use placeholders for configuration.
- Keep it small (maximum 12 files, each under 100 KB). Use only relative paths.
- Never claim legal/security certification or verified market demand.
"""
    system = (
        "You are a senior product engineer. Generate safe, maintainable starter code. "
        "Return strict JSON only, with no markdown fences. Treat all generated code as untrusted."
    )
    # A multi-file JSON package cannot fit in the default 2048-token report budget;
    # a truncated payload would never parse and the release would always fail.
    raw_text = provider.generate(system, prompt, max_tokens=FACTORY_MAX_OUTPUT_TOKENS)
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^\`{3}[^\n]*\n|\n\`{3}$", "", text)
    try:
        generated = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("AI output was not valid JSON; no release package was created") from exc
    files, warnings = _clean_files(generated.get("files"))
    if "README.md" not in files:
        files["README.md"] = f"# {name}\n\n{description}\n\nMVP starter package. Review before production use.\n"
    sample = generated.get("sample_data", {})
    files["SAMPLE_DATA.json"] = json.dumps(sample, ensure_ascii=False, indent=2) + "\n"
    summary = str(generated.get("summary", "MVP starter package"))[:1200]
    test_plan = generated.get("test_plan", [])
    if not isinstance(test_plan, list):
        test_plan = []
    timestamp = datetime.now(timezone.utc).isoformat()
    product_id = "prd-" + uuid4().hex[:12]
    release_dir = OUTPUT_ROOT / product_id / version
    release_dir.mkdir(parents=True, exist_ok=False)
    for relative, content in files.items():
        target = release_dir.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    (release_dir / "PRODUCT_SPEC.md").write_text(
        f"# Product specification: {name}\n\n{description}\n\n## MVP summary\n{summary}\n",
        encoding="utf-8",
    )
    (release_dir / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## {version} — {timestamp}\n- Initial AI-generated MVP package.\n",
        encoding="utf-8",
    )
    (release_dir / "QA_REPORT.md").write_text(
        "# QA report\n\n"
        + f"- Python syntax parse: {'PASS' if not any('syntax error' in w for w in warnings) else 'FAIL'} (not runtime-tested)\n"
        + "- Generated tests: included where supplied; not executed in the production worker.\n"
        + "- Security: static pattern scan only; human review required.\n"
        + "\n## Test plan\n" + "\n".join(f"- {str(item)[:300]}" for item in test_plan)
        + ("\n\n## Warnings\n" + "\n".join(f"- {w}" for w in warnings) if warnings else "\n\nNo static pattern warnings detected; this is not a security certification.\n"),
        encoding="utf-8",
    )
    manifest = {
        "product_id": product_id, "name": name, "version": version, "type": product_type,
        "created_at": timestamp, "summary": summary, "files": sorted(files),
        "warnings": warnings, "release_status": "review_required",
        "execution_policy": "generated source is never executed by the factory",
    }
    (release_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    zip_path = release_dir.parent / f"{product_id}-v{version}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(release_dir.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(release_dir))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    checksum_path = zip_path.with_suffix(".zip.sha256")
    checksum_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    backup = release_dir.parent / "backup"
    backup.mkdir(exist_ok=True)
    shutil.copy2(zip_path, backup / zip_path.name)
    return {
        **manifest, "download_path": str(zip_path), "checksum": digest,
        "checksum_path": str(checksum_path), "backup_path": str(backup / zip_path.name),
        "qa": {"syntax_parse": "pass" if not any("syntax error" in w for w in warnings) else "fail",
               "runtime_tests": "not_run", "security": "static_scan_only"},
    }


def product_metadata(product_id: str) -> dict:
    if not re.fullmatch(r"prd-[a-f0-9]{12}", product_id):
        raise FileNotFoundError(product_id)
    matches = list((OUTPUT_ROOT / product_id).glob("*/manifest.json"))
    if not matches:
        raise FileNotFoundError(product_id)
    return json.loads(matches[0].read_text(encoding="utf-8"))


def product_zip_path(product_id: str) -> Path:
    product_metadata(product_id)
    matches = list((OUTPUT_ROOT / product_id).glob("*.zip"))
    if not matches:
        raise FileNotFoundError(product_id)
    return matches[0]
