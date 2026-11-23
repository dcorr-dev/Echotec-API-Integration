"""EcoTech Solutions - Gestión operativa y financiera (ES3 · TI3021).

Ejecutar en una terminal real:  python3 main.py
(getpass oculta la contraseña solo en una terminal; algunos IDE no lo soportan).
"""
import getpass

import api_clients
import auth
import negocio
from config import logger, obtener_api_key, ocultar_secretos
from errores import ErrorAccesoDenegado, ErrorConfiguracion, ErrorEcoTech, ErrorValidacion
from validators import (
    validar_ciudad,
    validar_moneda,
    validar_monto,
    validar_pais,
    validar_password,
    validar_usuario,
)


class AplicacionEcoTech:
    """Aplicación de consola. El estado de sesión es privado y se verifica en un solo lugar."""

    def __init__(self) -> None:
        self._usuario_actual: str | None = None
        self._acciones = {
            "1": self._registrar,
            "2": self._iniciar_sesion,
            "3": self._consultar_clima,
            "4": self._consultar_tipo_cambio,
            "5": self._calcular_pago,
            "6": self._cerrar_sesion,
        }

    # ------------------------------------------------------------ sesión
    @property
    def autenticado(self) -> bool:
        return self._usuario_actual is not None

    def _exigir_sesion(self) -> None:
        """Control de acceso centralizado: toda función protegida empieza llamando a esto."""
        if not self.autenticado:
            raise ErrorAccesoDenegado()

    # ------------------------------------------------------------ opciones
    def _registrar(self) -> None:
        print("\n--- REGISTRO DE USUARIO ---")
        usuario = validar_usuario(input("Usuario: "))
        password = validar_password(getpass.getpass("Contraseña (no se muestra): "))
        if getpass.getpass("Repita la contraseña: ") != password:
            raise ErrorValidacion("Las contraseñas no coinciden.")
        auth.registrar_usuario(usuario, password)
        print(f"[ÉXITO] Usuario '{usuario}' registrado.")

    def _iniciar_sesion(self) -> None:
        if self.autenticado:
            print(f"[AVISO] Ya hay una sesión activa como '{self._usuario_actual}'.")
            return
        print("\n--- INICIO DE SESIÓN ---")
        usuario = input("Usuario: ")
        password = getpass.getpass("Contraseña: ")
        self._usuario_actual = auth.autenticar(usuario, password)
        print(f"[BIENVENIDO] Sesión iniciada como '{self._usuario_actual}'.")

    def _cerrar_sesion(self) -> None:
        if not self.autenticado:
            print("[AVISO] No hay una sesión activa.")
            return
        logger.info("Sesión cerrada: %s", self._usuario_actual)
        self._usuario_actual = None
        print("[INFO] Sesión cerrada.")

    def _consultar_clima(self) -> None:
        self._exigir_sesion()
        print("\n--- CLIMA DEL PROYECTO ---")
        api_key = obtener_api_key()
        if api_key is None:
            logger.error("Falta OPENWEATHER_API_KEY (revise el archivo .env)")
            raise ErrorConfiguracion("OPENWEATHER_API_KEY no definida")

        ciudad = validar_ciudad(input("Ciudad del proyecto: "))
        pais = validar_pais(input("Código de país de 2 letras (opcional, ej. CL): "))

        print("Consultando servicio meteorológico...")
        clima = api_clients.obtener_clima(ciudad, pais, api_key)
        logger.info("Consulta de clima (%s): %s", self._usuario_actual, clima["ciudad"])

        print(f"\nClima actual en {clima['ciudad']} ({clima['pais']}):")
        print(f"  * Temperatura : {clima['temperatura']:.1f} °C")
        print(f"  * Humedad     : {clima['humedad']} %")
        print(f"  * Estado      : {clima['descripcion'].capitalize()}")
        for alerta in negocio.evaluar_condiciones_proyecto(clima):
            print(f"  [ALERTA] {alerta}")

    def _consultar_tipo_cambio(self) -> None:
        self._exigir_sesion()
        print("\n--- TIPO DE CAMBIO ---")
        moneda = validar_moneda(input("Moneda (USD / EUR): "))

        print("Consultando indicadores económicos...")
        indicador = api_clients.obtener_indicador(moneda)
        logger.info("Consulta de %s (%s)", moneda, self._usuario_actual)

        print(f"\n1 {moneda} = $ {indicador['valor']:,.2f} CLP (fecha: {indicador['fecha']})")

    def _calcular_pago(self) -> None:
        self._exigir_sesion()
        print("\n--- CÁLCULO DE PAGO INTERNACIONAL ---")
        moneda = validar_moneda(input("Moneda del pago (USD / EUR): "))
        monto = validar_monto(input(f"Monto en {moneda}: "))

        print("Consultando indicadores económicos...")
        indicador = api_clients.obtener_indicador(moneda)
        total_clp = negocio.convertir_a_clp(monto, indicador["valor"])
        logger.info("Cálculo de pago (%s): %s %s", self._usuario_actual, monto, moneda)

        print(f"\n  * Monto          : {monto:,.2f} {moneda}")
        print(f"  * Tipo de cambio : $ {indicador['valor']:,.2f} CLP ({indicador['fecha']})")
        print(f"  * Equivalente    : $ {total_clp:,.2f} CLP")

    # ------------------------------------------------------------ menú
    def _mostrar_menu(self) -> None:
        estado = f"CONECTADO ({self._usuario_actual})" if self.autenticado else "NO AUTENTICADO"
        print("\n==============================================")
        print("   ECOTECH SOLUTIONS - GESTIÓN OPERATIVA")
        print(f"   Sesión: {estado}")
        print("==============================================")
        print("1. Registrar usuario")
        print("2. Iniciar sesión")
        print("3. Consultar clima            [requiere sesión]")
        print("4. Consultar tipo de cambio   [requiere sesión]")
        print("5. Calcular pago en CLP       [requiere sesión]")
        print("6. Cerrar sesión")
        print("0. Salir")

    def ejecutar(self) -> None:
        while True:
            self._mostrar_menu()
            opcion = input("\nSeleccione una opción: ").strip()
            if opcion == "0":
                print("Cerrando el sistema. ¡Hasta luego!")
                break
            accion = self._acciones.get(opcion)
            if accion is None:
                print("[OPCIÓN INVÁLIDA] Ingrese un número del menú.")
                continue
            try:
                accion()
            except ErrorEcoTech as exc:  # errores previstos: mensaje seguro al usuario
                print(f"[ERROR] {exc.mensaje_usuario}")
            except Exception as exc:  # última barrera: se registra (sin traza ni claves) y el menú sigue
                logger.error(
                    "Error inesperado en la opción %s: %s: %s",
                    opcion,
                    type(exc).__name__,
                    ocultar_secretos(str(exc)),
                )
                print("[ERROR] Ocurrió un error inesperado. El incidente fue registrado.")


def main() -> None:
    try:
        AplicacionEcoTech().ejecutar()
    except (KeyboardInterrupt, EOFError):
        print("\n[INFO] Programa interrumpido por el usuario.")


if __name__ == "__main__":
    main()
