import subprocess
import platform
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_mac_notification(title, message):
    if platform.system() != "Darwin":
        return False
    script = f'display notification "{message}" with title "{title}" sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        return True
    except Exception:
        return False


def send_email_reminder(to_email, subject, body, smtp_config=None):
    if not smtp_config or not to_email:
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_config.get("from_email", "")
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))
        server = smtplib.SMTP(smtp_config.get("host", "smtp.gmail.com"), smtp_config.get("port", 587))
        server.starttls()
        server.login(smtp_config.get("username", ""), smtp_config.get("password", ""))
        server.sendmail(msg["From"], to_email, msg.as_string())
        server.quit()
        return True
    except Exception:
        return False
