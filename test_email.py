import os, ssl, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from gpt_summarizer import generate_recap
from espn_fetcher import get_team_data
import html as _html

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

    league_id = 97124817
    team_id = 7
    week = 16

    team_data = get_team_data(league_id, team_id, week)
    recap = generate_recap(team_data)

    # Make sure it's a string
    recap = recap if isinstance(recap, str) else str(recap)

def recap_as_html(content: str) -> str:
    looks_like_html = ("<" in content and ">" in content) or content.strip().lower().startswith("<html")
    if looks_like_html:
        return content
    # Escape and keep newlines
    return f"<div style='white-space:pre-wrap'>{_html.escape(content)}</div>"

    text = f"LLM-Commissioner Recap\n\n{recap}"
    html = f"""<html><body>
    <h2>LLM-Commissioner</h2>
    {recap_as_html(recap)}
    </body></html>"""

    # Assuming msg is a MIMEMultipart("alternative")
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
