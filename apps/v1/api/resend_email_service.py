"""This module is used to send an email using Resend service."""

import resend

from config import aws_config, env_config
from core.utils.message_variable import InfoMessage

TEMPLATE_PATH = "assets/template/otp_email_verification.html"
FROM_EMAIL = env_config.RESEND_EMAIL_HOST


def load_template(otp: str, logo_image: str) -> str:
    """Load and populate OTP email HTML template."""
    with open(TEMPLATE_PATH, encoding="utf-8") as file:
        html = file.read()

    html = html.replace("{{OTP}}", otp)
    html = html.replace("{{logo_image}}", logo_image)
    return html


def build_plain_text(otp: str) -> str:
    """Build plain-text version of the OTP email for better deliverability."""
    return (
        f"Your Kuber Cab verification code is {otp}. "
        "It is valid for 2 minutes. Do not share this code with anyone.\n\n"
        "If you did not request this OTP, please ignore this email.\n"
        "For any queries, contact us at support@kubercab.in\n\n"
        "Thank you,\n"
        "Kuber Cab"
    )


def resolve_logo_url(logo_image: str | None = None) -> str:
    """Resolve a public HTTPS logo URL for the email body image."""
    for candidate in (logo_image, aws_config.KUBER_LOGO):
        if not candidate:
            continue
        cleaned = str(candidate).strip().strip('"').strip("'")
        if cleaned.startswith(("http://", "https://")):
            return cleaned
    return ""


def send_otp_email(
    to_email: str,
    otp: str,
    logo_image: str | None = None,
) -> bool:
    """
    Send OTP verification email using Resend.

    Uses a public logo URL in the HTML (no file attachment).

    Returns True if sent successfully, else False.
    """
    try:
        if not env_config.RESEND_API_KEY or not FROM_EMAIL:
            return False

        resend.api_key = env_config.RESEND_API_KEY
        from_email = (
            FROM_EMAIL
            if "<" in FROM_EMAIL
            else f"Kuber Cab <{FROM_EMAIL}>"
        )

        params: resend.Emails.SendParams = {
            "from": from_email,
            "to": [to_email],
            "subject": InfoMessage.emailTemplateSubject,
            "html": load_template(otp, resolve_logo_url(logo_image)),
            "text": build_plain_text(otp),
        }

        response = resend.Emails.send(params)
        return bool(response and response.get("id"))
    except Exception:
        return False
