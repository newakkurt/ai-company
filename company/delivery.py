"""Transactional digital product delivery after a verified payment."""
from email.message import EmailMessage

from .mailbox import MailConfig, _default_smtp


def send_product_delivery_email(
    recipient: str, buyer_name: str, product_name: str, download_url: str
) -> bool:
    cfg = MailConfig.from_env()
    if not cfg.configured or not recipient:
        return False
    message = EmailMessage()
    message["From"] = cfg.from_addr
    message["To"] = recipient
    message["Subject"] = f"Your {product_name} download is ready"
    greeting = f"Hello {buyer_name}," if buyer_name else "Hello,"
    message.set_content(
        f"{greeting}\n\n"
        f"Thank you for your purchase of {product_name}. Your secure download is ready:\n"
        f"{download_url}\n\n"
        "This link expires in 7 days and allows up to 5 downloads. "
        "Please keep it private. If you need help, reply to this email.\n"
    )
    with _default_smtp(cfg) as smtp:
        smtp.send_message(message)
    return True
