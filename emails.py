import ssl, smtplib
from os import environ as env
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SOURCE_EMAIL_ADDRESS = "caiotsan@gmail.com"
SOURCE_EMAIL_SERVICE = "gmail"
SOURCE_EMAIL_HOST    = "smtp.gmail.com"


class email_sender:

    def __init__(self, dry_run=False):
        self._context = ssl.create_default_context()
        self._server = smtplib.SMTP_SSL(SOURCE_EMAIL_HOST)

        if not dry_run:
            self._server.login(SOURCE_EMAIL_ADDRESS, env.get("SOURCE_EMAIL_PASSWORD"))

    def send(self, email, subject, content_html, content_text=""):
        # Create message container - the correct MIME type is multipart/alternative.
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SOURCE_EMAIL_ADDRESS
        msg['To'] = email

        # Record the MIME types of both parts - text/plain and text/html.
        part1 = MIMEText(content_text, 'plain')
        part2 = MIMEText(content_html.encode('utf-8'), 'html', 'utf-8')

        # Attach parts into message container.
        # According to RFC 2046, the last part of a multipart message, in this case
        # the HTML message, is best and preferred.
        msg.attach(part1)
        msg.attach(part2)
        self._server.sendmail(SOURCE_EMAIL_ADDRESS, email, msg.as_string())