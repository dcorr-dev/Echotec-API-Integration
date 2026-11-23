"""Registro e inicio de sesión.

- Las contraseñas NUNCA se guardan: solo su hash PBKDF2-HMAC-SHA256 con salt único.
- La comparación se hace en tiempo constante (hmac.compare_digest).
- Tras MAX_INTENTOS_LOGIN fallos la cuenta se bloquea SEGUNDOS_BLOQUEO segundos.
"""
import hashlib
import hmac
import json
import math
import os
import secrets
import time
from datetime import datetime, timezone

from config import (
    ARCHIVO_USUARIOS,
    LARGO_MAX_PASSWORD,
    MAX_INTENTOS_LOGIN,
    SEGUNDOS_BLOQUEO,
    logger,
)
from errores import (
    ErrorAlmacenamiento,
    ErrorCredenciales,
    ErrorCuentaBloqueada,
    ErrorValidacion,
)
from validators import validar_usuario

ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 600_000  # recomendación OWASP para PBKDF2-HMAC-SHA256

# Salt de relleno: se usa para gastar el mismo tiempo de cálculo cuando el
# usuario no existe o está bloqueado (evita enumerar usuarios por tiempo de respuesta).
_SALT_FALSO = secrets.token_bytes(16)

# Intentos fallidos de usuarios que NO existen (solo en memoria). Se bloquean igual
# que los reales para que el mensaje de bloqueo no revele qué usuarios existen.
_fallos_desconocidos: dict[str, dict] = {}


def _segundos_restantes(estado: dict, ahora: float) -> int:
    """Segundos que faltan para terminar el bloqueo (0 si no está bloqueado)."""
    return max(0, math.ceil(estado.get("bloqueado_hasta", 0) - ahora))


def _anotar_fallo(estado: dict, ahora: float) -> bool:
    """Suma un intento fallido. Devuelve True si con este fallo queda bloqueado."""
    estado["intentos_fallidos"] = estado.get("intentos_fallidos", 0) + 1
    if estado["intentos_fallidos"] >= MAX_INTENTOS_LOGIN:
        estado["bloqueado_hasta"] = ahora + SEGUNDOS_BLOQUEO
        estado["intentos_fallidos"] = 0
        return True
    return False


def _hash_password(password: str, salt: bytes, iteraciones: int | None = None) -> str:
    iteraciones = iteraciones or ITERACIONES
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iteraciones
    ).hex()


def cargar_usuarios() -> dict:
    """Lee usuarios.json. Si está dañado NO devuelve {} (para no sobrescribirlo después)."""
    if not ARCHIVO_USUARIOS.exists():
        return {}
    try:
        with open(ARCHIVO_USUARIOS, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("No se pudo leer usuarios.json (%s)", type(exc).__name__)
        raise ErrorAlmacenamiento("lectura de usuarios.json fallida") from None
    if not isinstance(datos, dict):
        logger.error("usuarios.json tiene una estructura inválida")
        raise ErrorAlmacenamiento("usuarios.json con estructura inválida")
    return datos


def guardar_usuarios(usuarios: dict) -> None:
    """Escritura atómica: se escribe un temporal y luego se reemplaza el original."""
    temporal = ARCHIVO_USUARIOS.with_suffix(".tmp")
    try:
        with open(temporal, "w", encoding="utf-8") as archivo:
            json.dump(usuarios, archivo, indent=4, ensure_ascii=False)
        os.replace(temporal, ARCHIVO_USUARIOS)
        os.chmod(ARCHIVO_USUARIOS, 0o600)  # solo el dueño puede leer/escribir
    except OSError as exc:
        logger.error("No se pudo guardar usuarios.json (%s)", type(exc).__name__)
        raise ErrorAlmacenamiento("escritura de usuarios.json fallida") from None


def registrar_usuario(usuario: str, password: str) -> None:
    """Registra un usuario ya validado. La contraseña se guarda solo como hash."""
    usuarios = cargar_usuarios()
    if usuario in usuarios:
        raise ErrorValidacion("El nombre de usuario no está disponible.")

    salt = secrets.token_bytes(16)
    usuarios[usuario] = {
        "algoritmo": ALGORITMO,
        "iteraciones": ITERACIONES,
        "salt": salt.hex(),
        "hash": _hash_password(password, salt),
        "intentos_fallidos": 0,
        "bloqueado_hasta": 0,
        "creado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    guardar_usuarios(usuarios)
    logger.info("Usuario registrado: %s", usuario)


def autenticar(usuario: str, password: str) -> str:
    """Valida credenciales. Devuelve el usuario si son correctas.

    - Credenciales incorrectas (usuario inexistente o clave mala): ErrorCredenciales,
      el mismo mensaje genérico en ambos casos.
    - Tras MAX_INTENTOS_LOGIN fallos: ErrorCuentaBloqueada (informa los segundos
      restantes). Se aplica igual a usuarios reales e inexistentes, así el bloqueo
      no revela qué usuarios existen.
    """
    try:
        usuario = validar_usuario(usuario)
    except ErrorValidacion:
        raise ErrorCredenciales() from None
    if not password or len(password) > LARGO_MAX_PASSWORD:
        raise ErrorCredenciales()

    usuarios = cargar_usuarios()
    registro = usuarios.get(usuario)
    ahora = time.time()

    if registro is None:
        # Usuario inexistente: mismo comportamiento que uno real (hash de relleno y bloqueo)
        estado = _fallos_desconocidos.setdefault(
            usuario, {"intentos_fallidos": 0, "bloqueado_hasta": 0}
        )
        _hash_password(password, _SALT_FALSO)
        restante = _segundos_restantes(estado, ahora)
        if restante > 0:
            raise ErrorCuentaBloqueada(restante)
        if _anotar_fallo(estado, ahora):
            raise ErrorCuentaBloqueada(SEGUNDOS_BLOQUEO)
        raise ErrorCredenciales()

    restante = _segundos_restantes(registro, ahora)
    if restante > 0:
        _hash_password(password, _SALT_FALSO)  # igualar tiempos
        logger.warning("Intento de login en cuenta bloqueada: %s", usuario)
        raise ErrorCuentaBloqueada(restante)

    try:
        salt = bytes.fromhex(registro["salt"])
        hash_guardado = str(registro["hash"])
        iteraciones = int(registro["iteraciones"])
    except (KeyError, ValueError, TypeError):
        logger.error("Registro de usuario dañado en usuarios.json: %s", usuario)
        raise ErrorAlmacenamiento("registro de usuario dañado") from None

    hash_calculado = _hash_password(password, salt, iteraciones)

    if hmac.compare_digest(hash_calculado, hash_guardado):
        registro["intentos_fallidos"] = 0
        registro["bloqueado_hasta"] = 0
        guardar_usuarios(usuarios)
        logger.info("Login correcto: %s", usuario)
        return usuario

    bloqueada = _anotar_fallo(registro, ahora)
    guardar_usuarios(usuarios)
    if bloqueada:
        logger.warning("Cuenta bloqueada temporalmente por intentos fallidos: %s", usuario)
        raise ErrorCuentaBloqueada(SEGUNDOS_BLOQUEO)
    logger.warning("Login fallido: %s", usuario)
    raise ErrorCredenciales()
