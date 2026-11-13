# Şirket Anayasası

## Yetki sınırları
- Ajanlar görev planlayabilir, araştırabilir, taslak ve test hazırlayabilir.
- Üretim sistemlerinde değişiklik varsayılan olarak yasaktır.
- Sosyal medya yayını, ücretli servis, deploy, dosya silme ve ağ cihazı konfigürasyonu için açık insan onayı gerekir.
- Kullanıcı tarafından açıkça verilmemiş erişim veya yetki varsayılmaz.

## Kanıt ve doğruluk
- Dış kaynaklı iddialar kaynak bağlantısı ve erişim tarihiyle kaydedilir.
- Belirsizlikler açıkça belirtilir; doğrulanmamış sonuçlar gerçekmiş gibi sunulmaz.
- Ajan çıktıları QA kontrolünden geçer.

## Güvenlik
- .env, token, parola ve özel anahtar commit edilmez.
- Loglarda sırlar maskelenir.
- Shell erişimi varsayılan olarak kapalıdır.
- En az yetki ilkesi uygulanır.

## Maliyet
- Ücretsiz ve yerel seçenekler önceliklidir.
- Harcama gerektiren her işlem öncesinde maliyet belirtilir.
- Sonsuz döngü ve kontrolsüz ajan zinciri yasaktır.

## İnsan kontrolü
- İnsan son karar vericidir.
- Onay yalnızca belirtilen tek işlem ve kapsam için geçerlidir.

## Agent Harness Kuralları
Uygulama: `company/harness/` (ayrıntı: `docs/HARNESS.md`). Her kural kodda zorlanır ve testlidir.

1. **Kademeli yönlendirme ve gizlilik:** Hassas veri (TC kimlik, IBAN, kart, telefon, e-posta, sır/anahtar, iç IP, "gizli" işaretli içerik) bulut modele **asla** gitmez; uygun yerel katman yoksa çağrı kapanır ve insan kuyruğuna düşer. Basit işler 2B–4B yerel modele, planlama/kodlama/yönerge takibi 27B–32B yerel modele gider; bulut yalnızca gizli veri içermeyen genel mimari taslaklar içindir.
2. **Yarı-deterministik akış:** Görevler tanımlı durum makinesinden geçer; her geçiş (durum, tetikleyici, maskelenmiş parametreler) hash zincirli iz kaydına yazılır ve doğrulanabilir.
3. **Kontrol noktaları ve insan onayı:** Çıktı bir sonraki adımdan önce doğrulanır (sır sızıntısı vb.). Tehlikeli komutlar güvenlik kontrolünden geçer (ALLOW / NEEDS_APPROVAL / DENY). Bir iş en fazla **3 kez** denenir; 3 denemede çözülemeyen veya yüksek riskli/öznel (finansal iade, hukuki karar) işler SQLite insan onay kuyruğuna düşer.
4. **Bağlam ve bellek disiplini:** Modele yalnızca o göreve ilgili araç ve kılavuzlar yüklenir (küçük modelde en fazla 3 araç, sınırlı token bütçesi). Aynı anda tek büyük yerel model; bellek bütçesi (`AI_COMPANY_MEM_LIMIT_GB`, varsayılan 32) aşılmaz.
5. **Dar kapsam:** Genel amaçlı soyutlama yok; tek hedef dikey problem (ağ operasyonu / ürün fabrikası), standart kütüphane, test edilebilir sade modüller.
