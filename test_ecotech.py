"""Pruebas automáticas (no usan internet: las respuestas de las APIs se simulan).

Ejecutar:  python3 -m unittest -v
"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

import api_clients
import auth
import main
import negocio
import validators
from errores import (
    ErrorAccesoDenegado,
    ErrorAutenticacionAPI,
    ErrorCredenciales,
    ErrorCuentaBloqueada,
    ErrorLimiteSolicitudes,
    ErrorNoEncontrado,
    ErrorRed,
    ErrorRespuestaInvalida,
    ErrorServidorExterno,
    ErrorValidacion,
)


class RespuestaFalsa:
    def __init__(self, codigo=200, datos=None, json_invalido=False):
        self.status_code = codigo
        self._datos = datos
        self._json_invalido = json_invalido

    def json(self):
        if self._json_invalido:
            raise ValueError("no es JSON")
        return self._datos


def sesion_con(respuesta=None, excepcion=None):
    sesion = MagicMock()
    if excepcion:
        sesion.get.side_effect = excepcion
    else:
        sesion.get.return_value = respuesta
    return sesion


CLIMA_OK = {
    "name": "Chillán",
    "sys": {"country": "CL"},
    "main": {"temp": 21.4, "humidity": 55},
    "weather": [{"description": "cielo claro"}],
}
DOLAR_OK = {"serie": [{"fecha": "2026-11-13T03:00:00.000Z", "valor": 950.5}]}


class PruebasValidadores(unittest.TestCase):
    def test_usuario(self):
        self.assertEqual(validators.validar_usuario("  dami_22 "), "dami_22")
        for malo in ["ab", "a" * 21, "con espacio", "ñandú_1", "ab!c_", "", "x'; DROP", None, 123]:
            with self.assertRaises(ErrorValidacion, msg=repr(malo)):
                validators.validar_usuario(malo)

    def test_password(self):
        self.assertEqual(validators.validar_password("Clave#2026x"), "Clave#2026x")
        for mala in ["Corta1#", "sinmayuscula1#", "SINMINUSCULA1#", "SinNumero##", "SinSimbolo123", "", None]:
            with self.assertRaises(ErrorValidacion, msg=repr(mala)):
                validators.validar_password(mala)

    def test_ciudad(self):
        for buena in ["Santiago", "San Nicolás", "Chillán", "O'Higgins", "Cabrero"]:
            self.assertEqual(validators.validar_ciudad(buena), buena)
        for mala in ["", " ", "---", "a", "Santiago123", "'; DROP--", "x" * 61, "Lima\nCusco&appid=1"]:
            with self.assertRaises(ErrorValidacion, msg=repr(mala)):
                validators.validar_ciudad(mala)

    def test_pais_y_moneda(self):
        self.assertIsNone(validators.validar_pais("  "))
        self.assertEqual(validators.validar_pais("cl"), "CL")
        with self.assertRaises(ErrorValidacion):
            validators.validar_pais("CHL")
        self.assertEqual(validators.validar_moneda(" usd "), "USD")
        with self.assertRaises(ErrorValidacion):
            validators.validar_moneda("XYZ")

    def test_monto(self):
        self.assertEqual(validators.validar_monto("1500"), Decimal("1500"))
        self.assertEqual(validators.validar_monto("1500,50"), Decimal("1500.50"))
        for malo in ["-5", "0", "nan", "inf", "1e9", "abc", "", "1.234", "99999999", "٣٣"]:
            with self.assertRaises(ErrorValidacion, msg=repr(malo)):
                validators.validar_monto(malo)


class PruebasApi(unittest.TestCase):
    def llamar_clima(self, **kw):
        with patch.object(api_clients, "_get_sesion", return_value=sesion_con(**kw)):
            return api_clients.obtener_clima("Chillán", "CL", "CLAVE_SECRETA")

    def test_clima_ok(self):
        clima = self.llamar_clima(respuesta=RespuestaFalsa(200, CLIMA_OK))
        self.assertEqual(clima["temperatura"], 21.4)
        self.assertEqual(clima["humedad"], 55)
        self.assertEqual(clima["ciudad"], "Chillán")

    def test_codigos_http(self):
        casos = {
            401: ErrorAutenticacionAPI,
            403: ErrorAutenticacionAPI,
            404: ErrorNoEncontrado,
            429: ErrorLimiteSolicitudes,
            500: ErrorServidorExterno,
            503: ErrorServidorExterno,
        }
        for codigo, esperado in casos.items():
            with self.assertRaises(esperado, msg=str(codigo)):
                self.llamar_clima(respuesta=RespuestaFalsa(codigo))

    def test_errores_de_red(self):
        with self.assertRaises(ErrorRed):
            self.llamar_clima(excepcion=requests.exceptions.ReadTimeout("lento"))
        with self.assertRaises(ErrorRed):
            self.llamar_clima(excepcion=requests.exceptions.ConnectionError("sin red"))

    def test_json_invalido_y_estructura(self):
        with self.assertRaises(ErrorRespuestaInvalida):
            self.llamar_clima(respuesta=RespuestaFalsa(200, json_invalido=True))
        with self.assertRaises(ErrorRespuestaInvalida):
            self.llamar_clima(respuesta=RespuestaFalsa(200, {"name": "X"}))
        with self.assertRaises(ErrorRespuestaInvalida):
            self.llamar_clima(respuesta=RespuestaFalsa(200, [1, 2, 3]))
        fuera = {**CLIMA_OK, "main": {"temp": 21, "humidity": 500}}
        with self.assertRaises(ErrorRespuestaInvalida):
            self.llamar_clima(respuesta=RespuestaFalsa(200, fuera))

    def test_indicador(self):
        with patch.object(api_clients, "_get_sesion", return_value=sesion_con(RespuestaFalsa(200, DOLAR_OK))):
            ind = api_clients.obtener_indicador("USD")
        self.assertEqual(ind["valor"], Decimal("950.5"))
        self.assertEqual(ind["fecha"], "2026-11-13")
        for malo in [{"serie": []}, {"serie": [{"fecha": "x", "valor": 1}]}, {"serie": [{"fecha": "2026-11-13T00", "valor": -3}]}, {}]:
            with patch.object(api_clients, "_get_sesion", return_value=sesion_con(RespuestaFalsa(200, malo))):
                with self.assertRaises(ErrorRespuestaInvalida, msg=repr(malo)):
                    api_clients.obtener_indicador("USD")

    def test_la_clave_no_aparece_en_el_log(self):
        with self.assertLogs("ecotech", level="WARNING") as capturado:
            with self.assertRaises(ErrorRed):
                self.llamar_clima(excepcion=requests.exceptions.ConnectionError("fallo en ...?q=X&appid=CLAVE_SECRETA&units=metric"))
            with self.assertRaises(ErrorAutenticacionAPI):
                self.llamar_clima(respuesta=RespuestaFalsa(401))
        self.assertNotIn("CLAVE_SECRETA", "\n".join(capturado.output))


class PruebasNegocio(unittest.TestCase):
    def test_conversion(self):
        self.assertEqual(negocio.convertir_a_clp(Decimal("1500"), Decimal("950.5")), Decimal("1425750.00"))
        with self.assertRaises(ErrorValidacion):
            negocio.convertir_a_clp(Decimal("0"), Decimal("950"))

    def test_alertas(self):
        lluvia = {"descripcion": "lluvia ligera", "temperatura": 10, "humedad": 95}
        self.assertEqual(len(negocio.evaluar_condiciones_proyecto(lluvia)), 2)
        self.assertEqual(negocio.evaluar_condiciones_proyecto({"descripcion": "cielo claro", "temperatura": 20, "humedad": 50}), [])


class PruebasAuth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / "usuarios.json"
        self.parches = [
            patch.object(auth, "ARCHIVO_USUARIOS", self.ruta),
            patch.object(auth, "ITERACIONES", 1000),  # rápido solo para pruebas
        ]
        for p in self.parches:
            p.start()
        auth._fallos_desconocidos.clear()

    def tearDown(self):
        for p in self.parches:
            p.stop()
        self.tmp.cleanup()

    def test_registro_login_y_hash(self):
        auth.registrar_usuario("damian_1", "Clave#2026x")
        contenido = self.ruta.read_text(encoding="utf-8")
        self.assertNotIn("Clave#2026x", contenido)  # la contraseña no se guarda
        self.assertEqual(auth.autenticar("damian_1", "Clave#2026x"), "damian_1")
        with self.assertRaises(ErrorValidacion):
            auth.registrar_usuario("damian_1", "Otra#Clave1")  # duplicado

    def test_mismo_error_para_todo_fallo(self):
        auth.registrar_usuario("damian_1", "Clave#2026x")
        for usuario, clave in [("damian_1", "mala"), ("noexiste", "Clave#2026x"), ("x'--", "a"), ("damian_1", "")]:
            with self.assertRaises(ErrorCredenciales):
                auth.autenticar(usuario, clave)

    def test_bloqueo_por_intentos_informa_segundos(self):
        auth.registrar_usuario("damian_1", "Clave#2026x")
        for _ in range(2):
            with self.assertRaises(ErrorCredenciales) as ctx:
                auth.autenticar("damian_1", "incorrecta")
            self.assertNotIsInstance(ctx.exception, ErrorCuentaBloqueada)
        with self.assertRaises(ErrorCuentaBloqueada) as ctx:  # el 3.er fallo bloquea y lo informa
            auth.autenticar("damian_1", "incorrecta")
        self.assertIn("segundos", ctx.exception.mensaje_usuario)
        with self.assertRaises(ErrorCuentaBloqueada):  # bloqueado: ni la clave correcta entra
            auth.autenticar("damian_1", "Clave#2026x")

    def test_usuario_inexistente_se_bloquea_igual(self):
        # Mismo comportamiento que un usuario real: el bloqueo no revela quién existe
        for _ in range(2):
            with self.assertRaises(ErrorCredenciales) as ctx:
                auth.autenticar("fantasma_1", "cualquiera")
            self.assertNotIsInstance(ctx.exception, ErrorCuentaBloqueada)
        with self.assertRaises(ErrorCuentaBloqueada):
            auth.autenticar("fantasma_1", "cualquiera")
        with self.assertRaises(ErrorCuentaBloqueada):
            auth.autenticar("fantasma_1", "otra")

    def test_el_bloqueo_termina(self):
        auth.registrar_usuario("damian_1", "Clave#2026x")
        for _ in range(3):
            with self.assertRaises(ErrorCredenciales):
                auth.autenticar("damian_1", "incorrecta")
        futuro = auth.time.time() + auth.SEGUNDOS_BLOQUEO + 1
        with patch.object(auth.time, "time", return_value=futuro):
            self.assertEqual(auth.autenticar("damian_1", "Clave#2026x"), "damian_1")

    def test_archivo_corrupto_no_se_sobrescribe(self):
        self.ruta.write_text("{esto no es json", encoding="utf-8")
        with self.assertRaises(Exception) as ctx:
            auth.registrar_usuario("damian_1", "Clave#2026x")
        self.assertEqual(type(ctx.exception).__name__, "ErrorAlmacenamiento")
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), "{esto no es json")


class PruebasMenu(unittest.TestCase):
    def test_funciones_protegidas_exigen_sesion(self):
        app = main.AplicacionEcoTech()
        for funcion in (app._consultar_clima, app._consultar_tipo_cambio, app._calcular_pago):
            with self.assertRaises(ErrorAccesoDenegado):
                funcion()

    def test_el_menu_no_se_cae(self):
        app = main.AplicacionEcoTech()
        # 3 (sin sesión) -> 9 (opción inválida) -> 6 (sin sesión) -> 0 salir
        with patch("builtins.input", side_effect=["3", "9", "6", "0"]), patch("builtins.print") as salida:
            app.ejecutar()
        texto = " ".join(str(c.args[0]) for c in salida.call_args_list if c.args)
        self.assertIn("Acceso denegado", texto)
        self.assertIn("OPCIÓN INVÁLIDA", texto)

    def test_flujo_completo_con_apis_simuladas(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(auth, "ARCHIVO_USUARIOS", Path(tmp) / "usuarios.json"), \
                patch.object(auth, "ITERACIONES", 1000), \
                patch.dict("os.environ", {"OPENWEATHER_API_KEY": "CLAVE_SECRETA"}), \
                patch.object(api_clients, "_get_sesion") as get_sesion:
            get_sesion.return_value.get.side_effect = [
                RespuestaFalsa(200, CLIMA_OK),
                RespuestaFalsa(200, DOLAR_OK),
            ]
            claves = ["Clave#2026x", "Clave#2026x", "Clave#2026x"]  # registro, confirmación, login
            app = main.AplicacionEcoTech()
            with patch("builtins.input", side_effect=["1", "damian_1", "2", "damian_1", "3", "Chillán", "CL", "5", "USD", "1500", "0"]), \
                    patch("getpass.getpass", side_effect=claves), \
                    patch("builtins.print") as salida:
                app.ejecutar()
            texto = " ".join(str(c.args[0]) for c in salida.call_args_list if c.args)
        self.assertIn("registrado", texto)
        self.assertIn("Clima actual en Chillán", texto)
        self.assertIn("1,425,750.00", texto)


if __name__ == "__main__":
    unittest.main()
