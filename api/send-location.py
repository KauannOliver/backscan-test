# api/send-location.py
# Vercel Serverless Function (Python)
# Recebe latitude/longitude, faz reverse-geocoding e envia e-mail.

import json, os, requests, smtplib, logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ------------------------------------------------------- configuração
EMAIL_ORIGEM   = os.getenv("EMAIL_ORIGEM")   # ex.: kauanotavares123@gmail.com
EMAIL_DESTINO  = os.getenv("EMAIL_DESTINO")  # ex.: pckauann@gmail.com
APP_PASSWORD   = os.getenv("APP_PASSWORD")   # 16 caracteres, sem espaços
UA            = "BackScanApp/1.0 (kauanotavares123@gmail.com)"
TIMEOUT       = 10  # s

logging.basicConfig(level=logging.INFO)

# ------------------------------------------------------- utilidades
def geocode(lat: float, lon: float) -> dict | None:
    url = (
        "https://nominatim.openstreetmap.org/reverse"
        f"?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
    )
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        a = r.json().get("address", {})
        return {
            "rua": a.get("road") or "N/A",
            "bairro": a.get("suburb") or a.get("neighbourhood") or "N/A",
            "cidade": a.get("city") or a.get("town") or a.get("village") or "N/A",
            "estado": a.get("state") or "N/A",
            "pais": a.get("country") or "N/A",
        }
    except Exception as e:
        logging.error("Geocoding error: %s", e)
        return None


def format_email(lat: float, lon: float, e: dict) -> str:
    return (
        "Uma nova localização foi capturada:\n\n"
        f"Latitude:  {lat}\nLongitude: {lon}\n"
        f"Rua: {e['rua']}\nBairro: {e['bairro']}\n"
        f"Cidade: {e['cidade']}\nEstado: {e['estado']}\nPaís: {e['pais']}\n"
    )


def send_email(body: str) -> None:
    if not (EMAIL_ORIGEM and EMAIL_DESTINO and APP_PASSWORD):
        logging.warning("Credenciais de e-mail ausentes; não enviando.")
        return
    msg = MIMEMultipart()
    msg["From"], msg["To"] = EMAIL_ORIGEM, EMAIL_DESTINO
    msg["Subject"] = "Nova Localização Capturada - BackScan"
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=TIMEOUT) as smtp:
        smtp.login(EMAIL_ORIGEM, APP_PASSWORD)
        smtp.send_message(msg)
        logging.info("E-mail enviado para %s", EMAIL_DESTINO)

# ------------------------------------------------------- função Vercel
def handler(request, context):
    if request.method != "POST":
        return {"statusCode": 405, "body": "Method Not Allowed"}

    try:
        data = json.loads(request.body or "{}")
        lat, lon = float(data["latitude"]), float(data["longitude"])
    except Exception:
        return {"statusCode": 400, "body": json.dumps({"success": False, "error": "Payload inválido"})}

    endereco = geocode(lat, lon)
    if not endereco:
        return {"statusCode": 502, "body": json.dumps({"success": False, "error": "Reverse geocoding falhou"})}

    send_email(format_email(lat, lon, endereco))
    return {"statusCode": 200, "body": json.dumps({"success": True})}
