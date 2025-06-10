# api/send-location.py
#
# Vercel Serverless Function (Python runtime, Beta)
# ------------------------------------------------
# Recebe JSON { latitude, longitude } via POST,
# faz reverse-geocoding na Nominatim
# e envia e-mail com o endereço aproximado.
#
# Dependências (requirements.txt):
#   requests
#
# Nas variáveis de ambiente do projeto (Dashboard → Settings → Environment):
#   EMAIL_ORIGEM   → seu Gmail
#   EMAIL_DESTINO  → para onde o aviso será enviado
#   APP_PASSWORD   → App Password de 16 caracteres (sem espaços)
#
# Front-end: basta continuar chamando   fetch("/send-location", …)
#            — o rewrite para /api/send-location está em vercel.json.
#
# Docs do runtime: https://vercel.com/docs/functions/runtimes/python
# ------------------------------------------------

from http.server import BaseHTTPRequestHandler
import json, os, requests, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ----- Config --------------------------------------------------------------

EMAIL_ORIGEM   = os.getenv("EMAIL_ORIGEM")
EMAIL_DESTINO  = os.getenv("EMAIL_DESTINO")
APP_PASSWORD   = os.getenv("APP_PASSWORD")
UA             = "BackScanApp/1.0 (kauanotavares123@gmail.com)"
TIMEOUT        = 10  # segundos

def geocode(lat: float, lon: float) -> dict | None:
    url = (
        "https://nominatim.openstreetmap.org/reverse"
        f"?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
    )
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        addr = r.json().get("address", {})
        return {
            "rua":    addr.get("road") or "N/A",
            "bairro": addr.get("suburb") or addr.get("neighbourhood") or "N/A",
            "cidade": addr.get("city") or addr.get("town") or addr.get("village") or "N/A",
            "estado": addr.get("state") or "N/A",
            "pais":   addr.get("country") or "N/A",
        }
    except Exception:
        return None

def format_email(lat: float, lon: float, e: dict) -> str:
    return (
        "Uma nova localização foi capturada:\n\n"
        f"Latitude:  {lat}\n"
        f"Longitude: {lon}\n"
        f"Rua:       {e['rua']}\n"
        f"Bairro:    {e['bairro']}\n"
        f"Cidade:    {e['cidade']}\n"
        f"Estado:    {e['estado']}\n"
        f"País:      {e['pais']}\n"
    )

def send_email(body: str) -> None:
    if not (EMAIL_ORIGEM and EMAIL_DESTINO and APP_PASSWORD):
        # Credenciais ausentes: simplesmente não envia.
        return
    msg = MIMEMultipart()
    msg["From"], msg["To"] = EMAIL_ORIGEM, EMAIL_DESTINO
    msg["Subject"] = "Nova Localização Capturada - BackScan"
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=TIMEOUT) as smtp:
        smtp.login(EMAIL_ORIGEM, APP_PASSWORD)
        smtp.send_message(msg)

# ----- HTTP handler --------------------------------------------------------

class handler(BaseHTTPRequestHandler):
    """Implementação mínima para o runtime Python da Vercel."""

    def _send(self, status: int, body: str | dict, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")  # CORS
        self.end_headers()
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        self.wfile.write(body.encode())

    def do_OPTIONS(self):
        """Pré-flight CORS."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or "{}")
            lat = float(data["latitude"])
            lon = float(data["longitude"])
        except Exception:
            self._send(400, {"success": False, "error": "Payload inválido"})
            return

        endereco = geocode(lat, lon)
        if not endereco:
            self._send(502, {"success": False, "error": "Reverse geocoding falhou"})
            return

        send_email(format_email(lat, lon, endereco))
        self._send(200, {"success": True})
