import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import sys
import os
from dotenv import load_dotenv

load_dotenv()

def send_email(name: str, surname: str, sex: str, birthday: str, resume: str,  med_ins: str) -> str:
    sender_email = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver_email = os.getenv("EMAIL_RECEIVER")
    
    # Validar que las variables de entorno estén configuradas
    if not all([sender_email, password, receiver_email]):
        raise ValueError("Email credentials not configured. Please set EMAIL_SENDER, EMAIL_PASSWORD, and EMAIL_RECEIVER environment variables.")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Información de paciente - CuraAI 🤖"
    msg["From"] = sender_email
    msg["To"] = receiver_email
    text = "Este correo tiene formato HTML. Si no ves los estilos, abrilo en un cliente compatible."
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: white; margin: 0; padding: 20px;">
        <div style="display: flex; flex-direction: column; align-items: flex-start; max-width: 600px; background: #61A5C2; border-radius: 10px; padding: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
        <h1 style="color: white">CuraAI</h1>
        <h2 style="color: white;">Hola doctor/a, soy Cura, le envío la información del paciente.</h2>
        <p style="color: white;">Nombre: {name}</p>
        <p style="color: white;">Apellido: {surname}</p>
        <p style="color: white;">Fecha de nacimiento: {birthday}</p>
        <p style="color: white;">Cobertura médica: {med_ins}</p>
        <p style="color: white;">Sexo: {sex}</p>
        <p style="color: white;">Resumen de la situación del paciente: {resume}</p>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
