"""Jerarquía de excepciones del sistema EcoTech.

Cada excepción tiene un `mensaje_usuario` seguro (sin rutas, URLs ni claves).
El detalle técnico (`detalle`) solo se escribe en app.log, nunca en pantalla.

ErrorEcoTech
├── ErrorValidacion          (entrada del usuario inválida)
├── ErrorCredenciales        (login fallido)
│   └── ErrorCuentaBloqueada     (demasiados intentos: informa segundos restantes)
├── ErrorAccesoDenegado      (función protegida sin sesión)
├── ErrorConfiguracion       (falta la clave de API, etc.)
├── ErrorAlmacenamiento      (usuarios.json ilegible o no escribible)
└── ErrorServicioExterno     (cualquier falla de una API externa)
    ├── ErrorRed                 (timeout / sin conexión)
    ├── ErrorAutenticacionAPI    (HTTP 401 / 403)
    ├── ErrorNoEncontrado        (HTTP 404)
    ├── ErrorLimiteSolicitudes   (HTTP 429)
    ├── ErrorServidorExterno     (HTTP 5xx)
    └── ErrorRespuestaInvalida   (JSON malformado o estructura inesperada)
"""


class ErrorEcoTech(Exception):
    """Base de todos los errores controlados del sistema."""

    mensaje_usuario = "Ocurrió un error inesperado. Intente nuevamente."

    def __init__(self, detalle: str = "") -> None:
        super().__init__(detalle or self.mensaje_usuario)
        self.detalle = detalle


class ErrorValidacion(ErrorEcoTech):
    """La entrada del usuario no cumple el formato esperado."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje_usuario = mensaje  # estos mensajes son seguros de mostrar


class ErrorCredenciales(ErrorEcoTech):
    mensaje_usuario = (
        "Credenciales inválidas. Si el problema persiste, espere unos minutos "
        "e intente nuevamente."
    )


class ErrorCuentaBloqueada(ErrorCredenciales):
    """Demasiados intentos fallidos. Informa cuánto falta para volver a intentar."""

    def __init__(self, segundos: int) -> None:
        super().__init__(f"bloqueo temporal ({segundos} s)")
        self.segundos = segundos
        self.mensaje_usuario = (
            f"Demasiados intentos fallidos. Intente nuevamente en {segundos} segundos."
        )


class ErrorAccesoDenegado(ErrorEcoTech):
    mensaje_usuario = "Acceso denegado. Debe iniciar sesión para usar esta función."


class ErrorConfiguracion(ErrorEcoTech):
    mensaje_usuario = (
        "El sistema no está configurado correctamente (falta la clave del "
        "servicio). Contacte al administrador."
    )


class ErrorAlmacenamiento(ErrorEcoTech):
    mensaje_usuario = (
        "No se pudo acceder a los datos locales del sistema. "
        "Contacte al administrador."
    )


class ErrorServicioExterno(ErrorEcoTech):
    mensaje_usuario = (
        "El servicio externo no está disponible en este momento. "
        "Intente más tarde."
    )


class ErrorRed(ErrorServicioExterno):
    mensaje_usuario = (
        "No se pudo conectar con el servicio externo. Revise su conexión a "
        "internet e intente nuevamente."
    )


class ErrorAutenticacionAPI(ErrorServicioExterno):
    mensaje_usuario = (
        "El servicio externo rechazó las credenciales del sistema. "
        "Contacte al administrador."
    )


class ErrorNoEncontrado(ErrorServicioExterno):
    mensaje_usuario = (
        "No se encontró la información solicitada. Verifique la ciudad o el "
        "país ingresado."
    )


class ErrorLimiteSolicitudes(ErrorServicioExterno):
    mensaje_usuario = (
        "Se superó el límite de consultas del servicio. Espere unos minutos "
        "e intente nuevamente."
    )


class ErrorServidorExterno(ErrorServicioExterno):
    mensaje_usuario = (
        "El servicio externo presenta fallas. Intente nuevamente más tarde."
    )


class ErrorRespuestaInvalida(ErrorServicioExterno):
    mensaje_usuario = (
        "El servicio externo devolvió datos inesperados. "
        "Intente nuevamente más tarde."
    )
