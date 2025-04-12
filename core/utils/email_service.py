"""This module is responsible for the email sending functionality."""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import BytesIO
from typing import Union

from fastapi import BackgroundTasks, UploadFile
from fastapi_mail import FastMail, MessageSchema, MessageType
from jinja2 import Environment

from config import mail_config


class EmailService:

    def send_email_service(self, background_tasks: BackgroundTasks, subject: str, email_to: Union[str, list[str]], body: dict, html_file: str):
        """
        Sends a simple email using FastMail.

        Args:
            subject (str): The subject of the email.
            email_to (Union[str, list[str]]): The recipient(s) of the email.
            body (dict): The email body content.
            html_file (str): The HTML template file name.

        Returns:
            None
        """
        email_to = [email_to] if isinstance(email_to, str) else email_to

        message = MessageSchema(
            subject=subject,
            recipients=email_to,
            template_body=body,
            subtype=MessageType.html
        )

        fm = FastMail(mail_config.conf)
        background_tasks.add_task(fm.send_message, message, template_name=html_file)

    def prepare_email_list(self, emails: Union[str, list[str]]) -> list:
        """
        Prepare a list of email addresses by splitting the input
        string and removing any leading or trailing whitespace.

        Args:
            email (Union[str, list[str]]): email addresses.

        Returns:
            list: A list of EmailStr objects representing the email addresses.
        """
        if isinstance(emails, str):
            emails = emails.split(",")
        return [email.strip() for email in emails]

    def send_mail(
        self,
        subject: str,
        render_args: dict,
        html_file: str,
        receiver_email: str,
        sender_email: str = mail_config.SENDER_EMAIL
    ):
        """
        This function is used to send email with respect
        to render information & html file.

        Args:
            render_args(dict): render arguments
            subject(str): The email subject
            html_file(str): Html file name
            receiver_email(str): The email address of recipient

        Returns:
            send a reset password email to user
        """
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = sender_email
        message["To"] = receiver_email

        if html_file:
            html = open(f"{os.getcwd()}\\assets\\template\\{html_file}").read()
            # Create a text/html message from a rendered subject
            message.attach(
                MIMEText(Environment().from_string(html).render(**render_args), "html")
            )

        # Attach plain text content
        if "body" in render_args:
            plain_text = render_args["body"]
            message.attach(MIMEText(plain_text, "plain"))

        # Send email
        with smtplib.SMTP(mail_config.SMTP_SERVER, mail_config.SMTP_PORT) as server:
            server.starttls()
            server.login(mail_config.SMTP_USERNAME, mail_config.SMTP_PASSWORD)
            server.sendmail(
                sender_email,
                receiver_email,
                message.as_string().encode("utf-8"),
            )
