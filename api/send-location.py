# api/send-location.py
# Vercel – Python runtime (beta)
# POST JSON {"latitude": ..., "longitude": ...}
# → faz reverse-geocoding na Nominatim
# → envia e-mail com o endereço aproximado.

from http.server import BaseHTTPRequestHandler
import os, json, logging, requests, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ------------------------------------------------------------------ config
EMAIL_ORIGEM  = os.getenv("EMAIL_ORIGEM")        # ex.: kauanotavares123@gmail.com
EMAIL_DESTINO = os.getenv("EMAIL_DESTINO")       # ex.: pckauann@gmail.com
APP_PASSWORD  = os.getenv("APP_PASSWORD")        # 16 caracteres, sem espaços
UA      = "BackScanApp/1.0 (kauanotavares123@gmail.com)"
TIMEOUT = 10  # segundos

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------- util
def geocode(lat: float, lon: float) -> dict | None:
    """Consulta Nominatim e devolve componentes de endereço (ou None)."""
    url = (
        "https://nominatim.openstreetmap.org/reverse"
        f"?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
    )
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        a = r.json().get("address", {})
        return {
            "rua":    a.get("road") or "N/A",
            "bairro": a.get("suburb") or a.get("neighbourhood") or "N/A",
            "cidade": a.get("city") or a.get("town") or a.get("village") or "N/A",
            "estado": a.get("state") or "N/A",
            "pais":   a.get("country") or "N/A",
        }
    except Exception as e:
        logging.error("Geocoding error: %s", e)
        return None


def format_email(lat: float, lon: float, e: dict) -> str:
    """Monta corpo de e-mail amigável."""
    return (
        "Uma nova localização foi capturada:\n\n"
        f"Latitude:  {lat}\nLongitude: {lon}\n"
        f"Rua: {e['rua']}\nBairro: {e['bairro']}\n"
        f"Cidade: {e['cidade']}\nEstado: {e['estado']}\nPaís: {e['pais']}\n"
    )


def send_email(body: str) -> None:
    """Envia e-mail via SMTP-SSL do Gmail."""
    if not (EMAIL_ORIGEM and EMAIL_DESTINO and APP_PASSWORD):
        logging.warning("Credenciais ausentes – e-mail não enviado.")
        return

    msg = MIMEMultipart()
    msg["From"], msg["To"] = EMAIL_ORIGEM, EMAIL_DESTINO
    msg["Subject"] = "Nova Localização Capturada - BackScan"
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=TIMEOUT) as smtp:
        smtp.login(EMAIL_ORIGEM, APP_PASSWORD)
        smtp.send_message(msg)
        logging.info("E-mail enviado para %s", EMAIL_DESTINO)

# ---------------------------------------------------------------- handler
class handler(BaseHTTPRequestHandler):
    """Classe exigida pelo runtime da Vercel (subclasse de BaseHTTPRequestHandler)."""

    def _reply(self, status: int, payload: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")  # CORS
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    # Pré-flight CORS
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # POST principal
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data   = json.loads(self.rfile.read(length) or "{}")
            lat, lon = float(data["latitude"]), float(data["longitude"])
        except Exception as e:
            logging.error("Payload inválido: %s", e)
            self._reply(400, {"success": False, "error": "Payload inválido"})
            return

        endereco = geocode(lat, lon)
        if not endereco:
            self._reply(502, {"success": False, "error": "Reverse geocoding falhou"})
            return

        send_email(format_email(lat, lon, endereco))
        self._reply(200, {"success": True})
