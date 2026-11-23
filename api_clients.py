"""Clientes de las APIs externas: OpenWeatherMap (clima) y mindicador.cl (tipo de cambio).

Este módulo NO imprime nada: traduce cada falla a una excepción de la jerarquía
ErrorServicioExterno. Quien llama (main.py) decide qué mostrar al usuario.
El detalle técnico se registra en app.log con las claves enmascaradas.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError as ErrorConexionRequests
from requests.exceptions import RequestException, Timeout
from urllib3.util.retry import Retry

from config import MONEDAS, TIMEOUT_SEGUNDOS, logger, ocultar_secretos
from errores import (
    ErrorAutenticacionAPI,
    ErrorLimiteSolicitudes,
    ErrorNoEncontrado,
    ErrorRed,
    ErrorRespuestaInvalida,
    ErrorServicioExterno,
    ErrorServidorExterno,
    ErrorValidacion,
)

URL_CLIMA = "https://api.openweathermap.org/data/2.5/weather"
URL_INDICADORES = "https://mindicador.cl/api/{indicador}"

_sesion = None


def _get_sesion() -> requests.Session:
    """Sesión reutilizable con 1 reintento automático ante errores 5xx o de conexión."""
    global _sesion
    if _sesion is None:
        reintentos = Retry(
            total=1,
            backoff_factor=0.5,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,  # al agotar reintentos devuelve la respuesta, no una excepción
        )
        _sesion = requests.Session()
        _sesion.mount("https://", HTTPAdapter(max_retries=reintentos))
    return _sesion


def _error(clase, detalle: str) -> ErrorServicioExterno:
    """Registra el detalle técnico (enmascarado) y crea la excepción a lanzar."""
    logger.warning("%s: %s", clase.__name__, ocultar_secretos(detalle))
    return clase(detalle)


def _lanzar_por_codigo(codigo: int, servicio: str) -> None:
    detalle = f"{servicio}: HTTP {codigo}"
    if codigo in (401, 403):
        raise _error(ErrorAutenticacionAPI, detalle)
    if codigo == 404:
        raise _error(ErrorNoEncontrado, detalle)
    if codigo == 429:
        raise _error(ErrorLimiteSolicitudes, detalle)
    if codigo >= 500:
        raise _error(ErrorServidorExterno, detalle)
    raise _error(ErrorServicioExterno, f"{detalle} inesperado")


def _solicitar_json(url: str, servicio: str, params: dict | None = None) -> dict:
    """GET con timeout; valida conexión, código HTTP y JSON. Devuelve un dict."""
    try:
        respuesta = _get_sesion().get(url, params=params, timeout=TIMEOUT_SEGUNDOS)
    except Timeout as exc:  # va primero: ConnectTimeout es Timeout Y ConnectionError
        raise _error(ErrorRed, f"{servicio}: timeout ({type(exc).__name__})") from None
    except ErrorConexionRequests as exc:
        raise _error(ErrorRed, f"{servicio}: sin conexión ({type(exc).__name__})") from None
    except RequestException as exc:
        raise _error(
            ErrorServicioExterno,
            f"{servicio}: {type(exc).__name__}: {ocultar_secretos(str(exc))[:200]}",
        ) from None

    if respuesta.status_code != 200:
        _lanzar_por_codigo(respuesta.status_code, servicio)

    try:
        datos = respuesta.json()
    except ValueError:  # incluye requests.exceptions.JSONDecodeError
        raise _error(ErrorRespuestaInvalida, f"{servicio}: JSON inválido") from None
    if not isinstance(datos, dict):
        raise _error(ErrorRespuestaInvalida, f"{servicio}: el JSON no es un objeto")
    return datos


def obtener_clima(ciudad: str, pais: str | None, api_key: str) -> dict:
    """Clima actual de una ciudad (ya validada). Devuelve solo los campos necesarios."""
    consulta = f"{ciudad},{pais}" if pais else ciudad
    parametros = {"q": consulta, "appid": api_key, "units": "metric", "lang": "es"}
    datos = _solicitar_json(URL_CLIMA, "clima", parametros)

    try:
        temperatura = float(datos["main"]["temp"])
        humedad = int(datos["main"]["humidity"])
        descripcion = str(datos["weather"][0]["description"])
        nombre = str(datos["name"])
        codigo_pais = str(datos.get("sys", {}).get("country", pais or ""))
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        raise _error(ErrorRespuestaInvalida, "clima: estructura inesperada") from None

    # Verificación de consistencia lógica antes de usar los datos
    if not (-90 <= temperatura <= 60 and 0 <= humedad <= 100):
        raise _error(ErrorRespuestaInvalida, "clima: valores fuera de rango")

    return {
        "ciudad": nombre,
        "pais": codigo_pais,
        "temperatura": temperatura,
        "humedad": humedad,
        "descripcion": descripcion,
    }


def obtener_indicador(moneda: str) -> dict:
    """Valor en CLP y fecha de la moneda ('USD' o 'EUR'). El valor es Decimal."""
    indicador = MONEDAS.get(moneda)
    if indicador is None:  # defensa en profundidad: main.py ya validó la moneda
        raise ErrorValidacion("Moneda no soportada.")

    datos = _solicitar_json(URL_INDICADORES.format(indicador=indicador), "indicadores")

    try:
        ultimo = datos["serie"][0]  # la API entrega la serie con la fecha más reciente primero
        valor = Decimal(str(ultimo["valor"]))
        fecha = str(ultimo["fecha"])[:10]
        datetime.strptime(fecha, "%Y-%m-%d")  # verifica el formato de la fecha
    except (KeyError, IndexError, TypeError, ValueError, InvalidOperation):
        raise _error(ErrorRespuestaInvalida, "indicadores: estructura inesperada") from None

    if not valor.is_finite() or valor <= 0:
        raise _error(ErrorRespuestaInvalida, "indicadores: valor fuera de rango")

    return {"moneda": moneda, "valor": valor, "fecha": fecha}
