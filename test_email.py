import os, ssl, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))  # 465=SSL, 587=STARTTLS
SENDER = os.environ["SMTP_USER"]
PASS = os.environ["SMTP_PASS"]
RECIP = os.getenv("TEST_EMAIL", SENDER)

def send_test():
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "LLM-Commissioner Test Email"
    msg["From"] = SENDER
    msg["To"] = RECIP

    text = "This is a plain-text test email from GitHub Actions."
    html = """<html><body>
              <h2>LLM-Commissioner</h2>
              <p>This is a <b>HTML</b> test email from GitHub Actions.</p>
              </body></html>"""
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context()) as s:
            s.login(SENDER, PASS); s.sendmail(SENDER, [RECIP], msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(SENDER, PASS); s.sendmail(SENDER, [RECIP], msg.as_string())

    print(f"✅ Sent test email to {RECIP}")

if __name__ == "__main__":
    send_test()
