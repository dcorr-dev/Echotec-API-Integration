"""Validación y saneamiento de entradas del usuario.

Cada función devuelve el valor ya limpio o lanza ErrorValidacion con un
mensaje seguro de mostrar. Se usa lista blanca (solo se permite lo esperado)
y `fullmatch`, para que la expresión regular cubra el texto completo.
"""
import re
import string
import unicodedata
from decimal import Decimal

from config import LARGO_MAX_PASSWORD, MONEDAS
from errores import ErrorValidacion

MONTO_MAXIMO = Decimal("1000000")

_LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
_RE_USUARIO = re.compile(r"[A-Za-z0-9_]{4,20}")
_RE_CIUDAD = re.compile(rf"[{_LETRAS}]+(?:[ '\-][{_LETRAS}]+)*")
_RE_PAIS = re.compile(r"[A-Za-z]{2}")
_RE_MONTO = re.compile(r"[0-9]{1,7}(?:[.,][0-9]{1,2})?")


def _como_texto(valor, nombre: str) -> str:
    if not isinstance(valor, str):
        raise ErrorValidacion(f"{nombre} debe ser texto.")
    return unicodedata.normalize("NFC", valor)


def _limpiar(valor, nombre: str) -> str:
    """Normaliza Unicode y colapsa espacios, tabulaciones y saltos de línea."""
    return " ".join(_como_texto(valor, nombre).split())


def validar_usuario(valor) -> str:
    usuario = _limpiar(valor, "El usuario")
    if not _RE_USUARIO.fullmatch(usuario):
        raise ErrorValidacion(
            "Usuario inválido: use de 4 a 20 caracteres (letras sin tilde, "
            "números o guion bajo)."
        )
    return usuario


def validar_password(valor) -> str:
    """Política para REGISTRAR contraseñas (no se modifica el texto ingresado)."""
    password = _como_texto(valor, "La contraseña")
    cumple = (
        8 <= len(password) <= LARGO_MAX_PASSWORD
        and any(c.isupper() for c in password)
        and any(c.islower() for c in password)
        and any(c in "0123456789" for c in password)
        and any(c in string.punctuation for c in password)
    )
    if not cumple:
        raise ErrorValidacion(
            f"Contraseña débil: use de 8 a {LARGO_MAX_PASSWORD} caracteres con "
            "mayúscula, minúscula, número y símbolo."
        )
    return password


def validar_ciudad(valor) -> str:
    ciudad = _limpiar(valor, "La ciudad")
    if not 2 <= len(ciudad) <= 60 or not _RE_CIUDAD.fullmatch(ciudad):
        raise ErrorValidacion(
            "Ciudad inválida: use solo letras, espacios, guiones o apóstrofes "
            "(2 a 60 caracteres)."
        )
    return ciudad


def validar_pais(valor) -> str | None:
    """Código de país de 2 letras (opcional). Devuelve None si se deja vacío."""
    pais = _limpiar(valor, "El país")
    if pais == "":
        return None
    if not _RE_PAIS.fullmatch(pais):
        raise ErrorValidacion(
            "País inválido: use el código de 2 letras (ej. CL, AR, PE) o deje vacío."
        )
    return pais.upper()


def validar_moneda(valor) -> str:
    moneda = _limpiar(valor, "La moneda").upper()
    if moneda not in MONEDAS:
        raise ErrorValidacion(f"Moneda no soportada. Opciones: {', '.join(MONEDAS)}.")
    return moneda


def validar_monto(valor) -> Decimal:
    """Acepta solo números positivos con hasta 2 decimales (rechaza nan, inf, 1e9, negativos)."""
    texto = _limpiar(valor, "El monto")
    if not _RE_MONTO.fullmatch(texto):
        raise ErrorValidacion(
            "Monto inválido: ingrese solo números positivos, con hasta 2 "
            "decimales (ej. 1500 o 1500.50)."
        )
    monto = Decimal(texto.replace(",", "."))
    if monto <= 0 or monto > MONTO_MAXIMO:
        raise ErrorValidacion(
            f"El monto debe ser mayor que 0 y no superar {MONTO_MAXIMO:,.0f}."
        )
    return monto
