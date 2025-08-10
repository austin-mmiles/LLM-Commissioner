import os, ssl, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from gpt_summarizer import generate_recap
from espn_fetcher import get_team_data
import html as _html

# --- Env + defaults ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))  # 465=SSL, 587=STARTTLS
SENDER    = os.getenv("SMTP_USER")              # full Gmail address
PASS      = os.getenv("SMTP_PASS")              # 16-char Gmail App Password
RECIP     = os.getenv("TEST_EMAIL", SENDER)     # default to sender if not set

# OpenAI key must exist for generate_recap()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set. Add it locally or as an Actions secret.")

if not SENDER or not PASS:
    raise RuntimeError("SMTP_USER and/or SMTP_PASS not set. Use Gmail address and App Password.")

def recap_as_html(content: str) -> str:
    """Return content as safe HTML. If already HTML-ish, pass through."""
    if not isinstance(content, str):
        content = str(content)
    looks_like_html = ("<" in content and ">" in content) or content.strip().lower().startswith("<html")
    if looks_like_html:
        return content
    # Escape and preserve newlines
    return f"<div style='white-space:pre-wrap; font-family:system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif'>{_html.escape(content)}</div>"

def send_test():
    # Build email container: use "alternative" so clients prefer HTML but have a plaintext fallback
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "LLM-Commissioner Recap"
    msg["From"] = SENDER
    msg["To"] = RECIP

    # --- Inputs (hardcoded for now; swap to args/env as needed) ---
    league_id = 97124817
    team_id = 7
    week = 16

    # --- Fetch + summarize ---
    team_data = get_team_data(league_id, team_id, week)
    recap = generate_recap(team_data)  # must be able to call OpenAI

    text = f"LLM-Commissioner Recap\n\n{recap}"
    html = f"""<html><body>
      <h2 style="margin:0 0 12px 0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif">LLM-Commissioner</h2>
      {recap_as_html(recap)}
    </body></html>"""

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    # --- Send ---
    context = ssl.create_default_context()
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as s:
            s.set_debuglevel(1)  # helpful in Actions logs
            s.login(SENDER, PASS)
            s.sendmail(SENDER, [RECIP], msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.set_debuglevel(1)
            s.ehlo()
            s.starttls(context=context)
            s.ehlo()
            s.login(SENDER, PASS)
            s.sendmail(SENDER, [RECIP], msg.as_string())

    print(f"✅ Sent test email to {RECIP}")

if __name__ == "__main__":
    send_test()
