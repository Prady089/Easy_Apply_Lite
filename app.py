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
    "SMTP_EMAIL": "",
    "SMTP_PASSWORD": "",
    "SMTP_SERVER": "smtp.gmail.com",
    "SMTP_PORT": "587",
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

def send_email_via_smtp(to_email, cc_email, subject, body, resume_filename):
    smtp_email = settings["SMTP_EMAIL"]
    smtp_password = settings["SMTP_PASSWORD"]
    smtp_server = settings["SMTP_SERVER"]
    smtp_port = int(settings["SMTP_PORT"])
    if not smtp_email or not smtp_password:
        raise RuntimeError("SMTP credentials not set")
    msg = MIMEMultipart()
    msg["From"] = smtp_email
    msg["To"] = to_email
    if cc_email:
        msg["Cc"] = cc_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if resume_filename and resume_filename != "(No attachment)":
        path = os.path.join(RESUME_FOLDER, resume_filename)
        mime, _ = mimetypes.guess_type(path)
        main, sub = (mime or "application/octet-stream").split("/", 1)
        with open(path, "rb") as f:
            part = MIMEBase(main, sub)
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=resume_filename)
        msg.attach(part)
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(msg)

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

def save_settings_ui(smtp_email, smtp_password, smtp_server, smtp_port, pin, email_body):
    global settings
    settings["SMTP_EMAIL"] = smtp_email
    settings["SMTP_PASSWORD"] = smtp_password
    settings["SMTP_SERVER"] = smtp_server
    settings["SMTP_PORT"] = smtp_port
    settings["ACCESS_PIN"] = pin
    settings["EMAIL_BODY"] = email_body
    save_settings(settings)
    return "✅ Settings saved."

with gr.Blocks(title="Job Application Assistant (SMTP)") as demo:
    with gr.Tab("Login"):
        with gr.Column() as pin_block:
            gr.Markdown("### 🔐 Enter Access PIN")
            pin_input = gr.Textbox(type="password")
            unlock_btn = gr.Button("Unlock")
        with gr.Column(visible=False) as app_block:
            gr.Markdown("## Job Application Assistant (SMTP)")
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
        gr.Markdown("### ⚙️ Configure SMTP, PIN, and Email Body")
        smtp_email = gr.Textbox(label="SMTP Email", value=settings["SMTP_EMAIL"])
        smtp_password = gr.Textbox(label="SMTP Password", type="password", value=settings["SMTP_PASSWORD"])
        smtp_server = gr.Textbox(label="SMTP Server", value=settings["SMTP_SERVER"])
        smtp_port = gr.Textbox(label="SMTP Port", value=settings["SMTP_PORT"])
        pin = gr.Textbox(label="Access PIN", type="password", value=settings["ACCESS_PIN"])
        email_body = gr.Textbox(label="Email Body", lines=12, value=settings["EMAIL_BODY"])
        save_btn = gr.Button("Save Settings")
        save_status = gr.Textbox(label="Status")
        save_btn.click(
            save_settings_ui,
            inputs=[smtp_email, smtp_password, smtp_server, smtp_port, pin, email_body],
            outputs=save_status
        )

demo.queue()
demo.launch(server_name="0.0.0.0", server_port=10000)
