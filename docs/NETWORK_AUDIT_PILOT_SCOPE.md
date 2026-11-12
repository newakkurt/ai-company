# Combined Network Audit — Pilot Scope & Data Handling

**Version:** 1.0  
**Product mode:** Read-only, file-based configuration review  
**Initial vendors:** Cisco IOS-like, Huawei VRP-like, ArubaOS-CX / legacy ProCurve (rule coverage varies by syntax)

## Türkçe — Pilot kapsamı

### Dahil
- Müşterinin kendi cihazlarından aldığı, önceden temizlediği metin tabanlı yapılandırma dosyalarının incelenmesi.
- Tedarikçi tespiti, desteklenen kurallar ve her bulgu için ilgili yapılandırma satırları.
- Önem seviyesi, öneriler ve sınırlamalar içeren Markdown, HTML veya JSON raporu.
- Sentetik/sanitize edilmiş konfigürasyonlarla tekrarlanabilir testler.

### Hariç
- SSH, Telnet, SNMP veya API ile canlı cihaz bağlantısı.
- Komut çalıştırma, yapılandırma değiştirme, port kapatma/açma veya otomatik düzeltme.
- Penetrasyon testi, güvenlik sertifikası, canlı durum doğrulaması veya mevzuata uygunluk garantisi.
- Kısmi dosyada bulunmayan bir ayarın canlı cihazda kesinlikle bulunmadığı iddiası.

### Dosya paylaşmadan önce
- Parolaları, SNMP community değerlerini, private key'leri, pre-shared key'leri, kullanıcı adlarını ve gerçek IP adreslerini maskele.
- Yalnızca yetkili olduğun cihazlardan alınan dosyaları paylaş.
- Dosyanın tam mı, kısmi mi, sanitize edilmiş mi olduğunu belirt.

### Veri işleme
- Bu modül orijinal konfigürasyonu kalıcı olarak saklamaz.
- Rapor kanıtlarında parola, secret, community ve anahtar benzeri değerler [REDACTED] olarak maskelenir.
- Ham konfigürasyonun e-posta veya herkese açık bağlantıyla gönderilmesi istenmez.
- Nihai saklama/silme süresi müşteri sözleşmesinde ayrıca belirlenmelidir.

### Teslimat
- Yönetici özeti, bulgular, kanıt satırları, öneriler, varsayımlar ve sınırlamalar.
- Bulgular müşteri ağ sorumlusu tarafından doğrulanmadan değişiklik talimatı sayılmaz.

## English — Pilot scope

### Included
- Review of customer-supplied, pre-sanitized text configuration files.
- Best-effort vendor detection, supported text checks, and evidence lines.
- Markdown, HTML, or JSON report with severity, recommendations, assumptions, and limitations.
- Reproducible tests using synthetic/sanitized fixtures.

### Excluded
- SSH, Telnet, SNMP, or API connections to devices.
- Command execution, configuration changes, port shutdown/enablement, or automatic remediation.
- Penetration testing, security certification, live-state verification, or compliance guarantees.
- Claims that a directive absent from a partial file is definitely absent from the live device.

### Before sharing a file
- Remove passwords, SNMP communities, private keys, pre-shared keys, usernames, and real IP addresses.
- Share only configurations from devices you are authorized to assess.
- State whether the file is complete, partial, or sanitized.

### Data handling
- This module does not persist the original configuration text.
- Password-, secret-, community-, and key-like values are redacted from report evidence.
- Do not send raw configurations by email or public link for pilot delivery.
- Agree final retention/deletion periods explicitly in the customer engagement.

### Delivery
- Executive summary, findings, supporting evidence, recommendations, assumptions, and limitations.
- Findings are not change instructions; the customer's network owner must review and approve remediation.
