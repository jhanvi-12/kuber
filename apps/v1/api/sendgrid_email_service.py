"""This module is used to send an email using sendgrid service"""

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from config import env_config
from core.utils.message_variable import InfoMessage


TEMPLATE_PATH = "assets/template/otp_email_verification.html"
FROM_EMAIL = env_config.EMAIL_HOST_USER


def load_template(otp: str, logo_image: str) -> str:
    """Load and populate OTP email HTML template."""
    with open(TEMPLATE_PATH, encoding="utf-8") as file:
        html = file.read()

    html = html.replace("{{OTP}}", otp)
    html = html.replace("{{logo_image}}", logo_image)
    return html


def send_otp_email(
    to_email: str,
    otp: str,
    logo_image: str,
) -> bool:
    """
    Send OTP verification email using SendGrid.

    Returns True if sent successfully, else raises exception.
    """
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject=InfoMessage.emailTemplateSubject,
        html_content=load_template(otp, logo_image)
    )

    sg = SendGridAPIClient(env_config.SENDGRID_API_KEY)
    response = sg.send(message)

    if response.status_code != 202:
        return False

    return True
