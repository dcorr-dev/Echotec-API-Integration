"""Configuración central: rutas, constantes, variables de entorno y logging.

Las claves NUNCA se escriben en el código: se leen desde el archivo .env
(o desde variables de entorno del sistema).
"""
import logging
import os
import re
from pathlib import Path

def _cargar_env_manual(ruta: Path) -> None:
    """Lector mínimo de .env (líneas CLAVE=VALOR) para cuando python-dotenv no está instalado."""
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip().removeprefix("export ").strip()
        valor = valor.strip().strip("\"'")
        if clave:
            os.environ.setdefault(clave, valor)


_RUTA_ENV = Path(__file__).resolve().parent / ".env"
try:
    from dotenv import load_dotenv

    load_dotenv(_RUTA_ENV, encoding="utf-8-sig")
except ImportError:  # sin python-dotenv se usa el lector manual (el .env se lee igual)
    _cargar_env_manual(_RUTA_ENV)

BASE_DIR = Path(__file__).resolve().parent
ARCHIVO_USUARIOS = BASE_DIR / "usuarios.json"
ARCHIVO_LOG = BASE_DIR / "app.log"

# --- Red ---
TIMEOUT_SEGUNDOS = (3, 6)  # (conexión, lectura) en segundos

# --- Monedas soportadas: código ISO -> código del indicador en mindicador.cl ---
MONEDAS = {"USD": "dolar", "EUR": "euro"}

# --- Seguridad ---
MAX_INTENTOS_LOGIN = 3
SEGUNDOS_BLOQUEO = 60
LARGO_MAX_PASSWORD = 128


def obtener_api_key() -> str | None:
    """Devuelve la clave de OpenWeatherMap o None si no está configurada."""
    clave = os.getenv("OPENWEATHER_API_KEY", "").strip()
    return clave or None


def ocultar_secretos(texto: str) -> str:
    """Enmascara claves en cualquier texto antes de escribirlo en el log.

    Los mensajes de `requests` suelen incluir la URL completa, y la URL de
    OpenWeatherMap lleva la clave en el parámetro `appid`.
    """
    texto = re.sub(r"(appid=)[^&\s'\")]+", r"\1***", texto, flags=re.IGNORECASE)
    clave = obtener_api_key()
    if clave:
        texto = texto.replace(clave, "***")
    return texto


def configurar_logging() -> logging.Logger:
    """Crea el logger del sistema (escribe solo en app.log, no en pantalla)."""
    log = logging.getLogger("ecotech")
    if not log.handlers:
        log.setLevel(logging.INFO)
        manejador = logging.FileHandler(ARCHIVO_LOG, encoding="utf-8")
        manejador.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        log.addHandler(manejador)
        log.propagate = False
    return log


logger = configurar_logging()
