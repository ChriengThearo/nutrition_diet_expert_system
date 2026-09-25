import smtplib
from email.mime.text import MIMEText
from flask import current_app


class MailService:
    @staticmethod
    def send_verification_code(to_email: str, full_name: str, code: str) -> None:
        subject = "Verify your email - Diet Expert"
        body = (
            f"Hi {full_name},\n\n"
            f"Your verification code is: {code}\n\n"
            "This code expires in 15 minutes. If you didn't request this, you can ignore this email.\n\n"
            "- Diet Expert"
        )

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
        msg["To"] = to_email

        with smtplib.SMTP_SSL(current_app.config["MAIL_SERVER"], current_app.config["MAIL_PORT"]) as server:
            server.login(current_app.config["MAIL_USERNAME"], current_app.config["MAIL_PASSWORD"])
            server.sendmail(current_app.config["MAIL_DEFAULT_SENDER"], [to_email], msg.as_string())
