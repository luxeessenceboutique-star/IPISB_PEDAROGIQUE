import os
import resend  # type: ignore[import]

resend.api_key = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@ipisb.ma")


def send_email(to: str | list[str], subject: str, html: str) -> None:
    """
    Send a transactional email via Resend.
    Silently skips if RESEND_API_KEY is not configured.
    Never raises — email failures must never break the main operation.
    """
    if not resend.api_key:
        return
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "html": html,
        })
    except Exception:
        pass
