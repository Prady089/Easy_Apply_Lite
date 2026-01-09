
import os
import re
import time
import mimetypes
import gradio as gr
import smtplib
import json

from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email import encoders


SETTINGS_FILE = "settings.json"
RESUME_FOLDER = "."
ALLOWED_RESUME_EXTENSIONS = (".pdf", ".docx", ".doc")
MIN_SECONDS_BETWEEN_GENERATE = 3
_last_generate_time = 0.0

DEFAULT_SETTINGS = {
    "ACCESS_PIN": "",
    "SENDGRID_API_KEY": "",
    "SMTP_EMAIL": "",
    "DEFAULT_PHONE": "+1-682-436-4050",
    "DEFAULT_LINKEDIN": "https://www.linkedin.com/in/prady089/",
    "DEFAULT_SUBJECT": "Job Application - Business Analyst",
    "EMAIL_BODY": """Hello,\n\nI hope this message finds you well. I came across your LinkedIn post regarding the Business Analyst position and would like to express my interest, as the role closely aligns with my experience and skill set.\n\nPlease find my resume attached for your review. I would appreciate it if you could let me know the next steps or if you require any additional information to process my application.\n\nKindly note that I am on H1B visa and Currently located in Dallas Texas, Open for Relocation.Thank you.\n\nRegards\nPradeep Kumar\n+1-682-436-4050\npradeepkumar089@gmail.com\nhttps://www.linkedin.com/in/prady089/"""
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in DEFAULT_SETTINGS.items():
            if k not in data:
                data[k] = v
        return data
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

settings = load_settings()
ACCESS_PIN = settings["ACCESS_PIN"]
DEFAULT_FROM_EMAIL = settings["SMTP_EMAIL"]
DEFAULT_PHONE = settings["DEFAULT_PHONE"]
DEFAULT_LINKEDIN = settings["DEFAULT_LINKEDIN"]
DEFAULT_SUBJECT = settings["DEFAULT_SUBJECT"]
STATIC_BODY = settings["EMAIL_BODY"]

def ensure_folders():
    # No need to create folder if using root
    pass

def list_resume_files():
    ensure_folders()
    return sorted(
        [f for f in os.listdir(RESUME_FOLDER) if f.lower().endswith(ALLOWED_RESUME_EXTENSIONS)]
    )

def get_default_resume():
    preferred = "Pradeep Kumar BA.docx"
    files = list_resume_files()
    return preferred if preferred in files else "(No attachment)"

def extract_email_and_role(text: str):
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    email = email_match.group(0) if email_match else ""
    role_match = re.search(r"(Role|Position|Opening|Job Title)[:\-]\s*([^\n\r]+)", text, re.I)
    role = role_match.group(2).strip() if role_match else "Business Analyst"
    return email, role

def generate_email(linkedin_post, to_email, cc_email):
    global _last_generate_time, settings
    if time.time() - _last_generate_time < MIN_SECONDS_BETWEEN_GENERATE:
        return to_email, cc_email, "", "⏳ Please wait", ""
    _last_generate_time = time.time()
    extracted_to, role = extract_email_and_role(linkedin_post)
    subject = f"Job Application - {role}"
    return (
        to_email or extracted_to,
        cc_email,
        subject,
        "✅ Draft generated",
        settings["EMAIL_BODY"]
    )

import requests
import base64
def send_email_via_smtp(to_email, cc_email, subject, body, resume_filename):
    api_key = settings.get("SENDGRID_API_KEY", "")
    from_email = settings["SMTP_EMAIL"]
    if not api_key or not from_email:
        raise RuntimeError("SendGrid API key or sender email not set")
    data = {
        "personalizations": [
            {
                "to": [{"email": to_email}],
                "subject": subject
            }
        ],
        "from": {"email": from_email},
        "content": [
            {"type": "text/plain", "value": body}
        ]
    }
    if cc_email:
        data["personalizations"][0]["cc"] = [{"email": cc_email}]
    files = None
    if resume_filename and resume_filename != "(No attachment)":
        path = os.path.join(RESUME_FOLDER, resume_filename)
        with open(path, "rb") as f:
            file_data = f.read()
        encoded = base64.b64encode(file_data).decode()
        mime, _ = mimetypes.guess_type(path)
        data["attachments"] = [
            {
                "content": encoded,
                "type": mime or "application/octet-stream",
                "filename": resume_filename
            }
        ]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    r = requests.post("https://api.sendgrid.com/v3/mail/send", json=data, headers=headers)
    if r.status_code >= 400:
        raise RuntimeError(f"SendGrid error: {r.status_code} {r.text}")

def verify_pin(pin):
    if settings["ACCESS_PIN"] and pin != settings["ACCESS_PIN"]:
        raise gr.Error("❌ Invalid PIN")

def refresh_resumes():
    return gr.update(
        choices=["(No attachment)"] + list_resume_files(),
        value=get_default_resume()
    )

def send_email_ui(to, cc, subject, body, resume):
    send_email_via_smtp(
        to, cc, subject, body,
        None if resume == "(No attachment)" else resume
    )
    return "", "", "", "✅ Email sent. Ready for next JD.", ""

ensure_folders()

def save_settings_ui(sendgrid_api_key, smtp_email, pin, email_body):
    global settings
    settings["SENDGRID_API_KEY"] = sendgrid_api_key
    settings["SMTP_EMAIL"] = smtp_email
    settings["ACCESS_PIN"] = pin
    settings["EMAIL_BODY"] = email_body
    save_settings(settings)
    return "✅ Settings saved."


with gr.Blocks(title="Job Application Assistant") as demo:
    with gr.Tab("Login"):
        with gr.Column() as pin_block:
            gr.Markdown("### 🔐 Enter Access PIN")
            pin_input = gr.Textbox(type="password")
            unlock_btn = gr.Button("Unlock")
        with gr.Column(visible=False) as app_block:
            gr.Markdown("## Job Application Assistant (No AI)")
            linkedin_post = gr.Textbox(label="Paste LinkedIn Post", lines=10)
            generate_btn = gr.Button("Generate Email", variant="primary")
            to_email = gr.Textbox(label="To")
            cc_email = gr.Textbox(label="CC (Optional)")
            resume = gr.Dropdown(
                label="Attach Resume",
                choices=["(No attachment)"] + list_resume_files(),
                value=get_default_resume()
            )
            subject = gr.Textbox(label="Subject")
            body = gr.Textbox(label="Email Body", lines=12)
            status = gr.Textbox(label="Status")
            with gr.Row():
                refresh_btn = gr.Button("Refresh Resumes")
                send_btn = gr.Button("Send Email")
            refresh_btn.click(refresh_resumes, outputs=resume)
            generate_btn.click(
                generate_email,
                inputs=[linkedin_post, to_email, cc_email],
                outputs=[to_email, cc_email, subject, status, body]
            )
            send_btn.click(
                send_email_ui,
                inputs=[to_email, cc_email, subject, body, resume],
                outputs=[to_email, cc_email, subject, status, body]
            )
        unlock_btn.click(
            verify_pin,
            inputs=pin_input
        ).then(
            lambda: (gr.update(visible=False), gr.update(visible=True)),
            outputs=[pin_block, app_block]
        )
    with gr.Tab("Settings"):
        gr.Markdown("### ⚙️ Configure SendGrid, PIN, and Email Body")
        sendgrid_api_key = gr.Textbox(label="SendGrid API Key", type="password", value=settings.get("SENDGRID_API_KEY", ""))
        smtp_email = gr.Textbox(label="Sender Email (From)", value=settings["SMTP_EMAIL"])
        pin = gr.Textbox(label="Access PIN", type="password", value=settings["ACCESS_PIN"])
        email_body = gr.Textbox(label="Email Body", lines=12, value=settings["EMAIL_BODY"])
        save_btn = gr.Button("Save Settings")
        save_status = gr.Textbox(label="Status")
        save_btn.click(
            save_settings_ui,
            inputs=[sendgrid_api_key, smtp_email, pin, email_body],
            outputs=save_status
        )

demo.queue()
demo.launch(server_name="0.0.0.0", server_port=10000)
