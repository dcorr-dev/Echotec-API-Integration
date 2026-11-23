---
typora-root-url: ./Capturas
---

# EcoTech Solutions – Integración de servicios externos

**Evaluación Sumativa 3 · TI3021 Programación Orientada a Objeto Seguro · Unidad 3**
Autor: Damián Correa · Carrera: Ingeniería en Informática

Script en Python (consola) que extiende el sistema de gestión de EcoTech Solutions con:

- Consulta del **clima** de la ciudad del proyecto (OpenWeatherMap) para apoyar la planificación.
- Consulta de **tipo de cambio** USD/EUR → CLP (mindicador.cl) y **cálculo de pagos** en moneda extranjera.
- **Login** con contraseñas hasheadas, **validación** de entradas y **manejo de errores** sin exponer información sensible.
- Documentación del **uso de IA** en el desarrollo (sección 6).

---

## 1. Puesta en marcha

Requiere Python 3.10 o superior.

```bash
cd DCORREA
python3 -m venv venv                  # entorno virtual (necesario en Arch/Linux modernos)
source venv/bin/activate              # en Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                  # en Windows: copy .env.example .env
# editar .env y pegar la clave real de OpenWeatherMap en OPENWEATHER_API_KEY
python3 main.py
```

- La clave gratuita se obtiene registrándose en <https://openweathermap.org/api>. Una clave nueva puede tardar un rato en activarse; mientras tanto la API responde 401 y el sistema lo informa sin caerse.
- mindicador.cl es pública y **no requiere clave**.
- Ejecutar en una **terminal real**: `getpass` oculta la contraseña solo ahí.
- Si falta `python-dotenv`, el programa igual funciona leyendo variables de entorno del sistema (`export OPENWEATHER_API_KEY=...`).

Pruebas automáticas (no usan internet, las APIs se simulan):

```bash
python3 -m unittest -v
```

## 2. Estructura del proyecto

| Archivo | Responsabilidad |
|---|---|
| `main.py` | Menú de consola y control de sesión (clase `AplicacionEcoTech`). |
| `auth.py` | Registro y login: hash PBKDF2 + salt, bloqueo temporal, persistencia en `usuarios.json`. |
| `validators.py` | Validación y saneamiento de usuario, contraseña, ciudad, país, moneda y monto. |
| `api_clients.py` | Consumo de OpenWeatherMap y mindicador.cl con `requests`; traduce fallas a excepciones. |
| `negocio.py` | Conversión de pagos a CLP (con `Decimal`) y alertas operativas según el clima. |
| `errores.py` | Jerarquía de excepciones propias con mensajes seguros para el usuario. |
| `config.py` | Rutas, constantes, lectura de `.env`, logging y enmascarado de claves. |
| `test_ecotech.py` | 22 pruebas automáticas. |
| `.env.example` | Plantilla de configuración (sin claves reales). |
| `usuarios.json`, `app.log` | Se generan al ejecutar (datos locales y registro técnico). |

## 3. Funcionamiento

1. **Registrar usuario** → valida formato, exige contraseña robusta y confirmación, guarda solo el hash.
2. **Iniciar sesión** → comprueba credenciales; tras 3 fallos bloquea el acceso 60 segundos (`SEGUNDOS_BLOQUEO` en `config.py`) e informa cuánto falta para reintentar. El bloqueo se aplica igual a usuarios inexistentes, para no revelar qué usuarios existen.
3. **Consultar clima / tipo de cambio / calcular pago** → solo disponibles con sesión iniciada.
4. **Cerrar sesión** y **Salir**.

Ejemplo de integración: el pago de un trabajador en USD (`1500`) se convierte a CLP con el valor del día y se muestra junto a la fecha del indicador. La consulta de clima agrega alertas (lluvia, calor extremo, heladas, humedad alta) para decidir si reprogramar tareas.

## 4. Correspondencia con la rúbrica

| Indicador | Dónde se cumple |
|---|---|
| 3.1.1.I.1 Solicitudes HTTP con librerías oficiales | `api_clients._solicitar_json` (`requests`, `Session`, `timeout`, `params=`, 1 reintento ante 5xx). |
| 3.1.1.I.2 Respuestas JSON | `respuesta.json()` con control de JSON inválido y de que sea un objeto. |
| 3.1.1.I.3 Extracción de datos | `obtener_clima` y `obtener_indicador` devuelven solo los campos necesarios. |
| 3.1.1.I.4 Integración y verificación | Conversión de tipos, rangos (humedad 0–100, temperatura, valor > 0), formato de fecha; uso en `negocio.py` y `main.py`. |
| 3.1.2.I.5 Autenticación con credenciales cifradas | `auth.py`: PBKDF2-HMAC-SHA256, 600.000 iteraciones, salt de 16 bytes, `hmac.compare_digest`. |
| 3.1.2.I.6 Validación y saneamiento | `validators.py`: listas blancas con `fullmatch`, normalización Unicode, límites de largo, `Decimal` para montos. |
| 3.1.2.I.7 Información sensible | Clave en `.env` (fuera del código), `.gitignore`, `usuarios.json` con permisos 600, claves enmascaradas en logs. |
| 3.1.2.I.8 Restricción de acceso | `AplicacionEcoTech._exigir_sesion()` al inicio de cada función protegida + bloqueo por intentos. |
| 3.1.3.I.9 Excepciones | Jerarquía en `errores.py`; `except` específicos; una única barrera final registrada. |
| 3.1.3.I.10 Red y timeouts | `timeout=(3, 6)`, `Timeout`/`ConnectionError` → `ErrorRed`, 1 reintento automático. |
| 3.1.3.I.11 Códigos HTTP | `_lanzar_por_codigo`: 401/403, 404, 429, 5xx y otros, cada uno con su excepción y mensaje. |
| 3.1.3.I.12 Continuidad y mensajes seguros | Mensajes genéricos al usuario, detalle técnico solo en `app.log`; el menú nunca se cierra por un error. |
| 3.1.4.I.13–16 IA | Sección 6 de este documento. |

## 5. Manejo de errores

| Situación | Excepción | Mensaje al usuario |
|---|---|---|
| Timeout o sin internet | `ErrorRed` | Revise su conexión e intente nuevamente. |
| HTTP 401 / 403 | `ErrorAutenticacionAPI` | El servicio rechazó las credenciales del sistema. |
| HTTP 404 | `ErrorNoEncontrado` | Verifique la ciudad o el país ingresado. |
| HTTP 429 | `ErrorLimiteSolicitudes` | Se superó el límite de consultas; espere unos minutos. |
| HTTP 5xx | `ErrorServidorExterno` | El servicio externo presenta fallas. |
| JSON inválido o campos faltantes | `ErrorRespuestaInvalida` | El servicio devolvió datos inesperados. |
| 3 intentos de login fallidos | `ErrorCuentaBloqueada` | Demasiados intentos fallidos. Intente nuevamente en N segundos. |
| Entrada inválida | `ErrorValidacion` | Mensaje específico del formato esperado. |
| Falta la clave en `.env` | `ErrorConfiguracion` | El sistema no está configurado correctamente. |
| `usuarios.json` dañado | `ErrorAlmacenamiento` | No se pudo acceder a los datos locales. |

Los detalles técnicos (código HTTP, tipo de excepción) se escriben en `app.log` con las claves reemplazadas por `***`.

---

## 6. Uso de herramientas de IA

### 6.1 Declaración

| Herramienta | Uso |
|---|---|
| **Gemini** | Generación inicial del código (Prompts 1 a 6). |
| **Claude** | Revisión crítica del código de Gemini, detección de fallas y refactorización final (Prompt 7). |

Método de trabajo: pedí el código a Gemini **por partes** (una función o módulo por prompt) y guardé cada prompt y respuesta. Luego usé Claude para revisar ese código contra la guía y la rúbrica, comprobar los problemas ejecutando casos de prueba y rehacer el proyecto de forma modular. El código final fue leído y probado por mí, aparte de leer y analizar todo el código hasta poder explicar el porqué de cada linea, hice un total de 20 pruebas considerando las que hice más adelante y problemas que tuve al hacer funcionar la api key en mi programa. Los fragmentos de Gemini que se mantuvieron y los que se modificaron o descartaron se detallan en 6.3.

### 6.2 Prompts, hallazgos y decisiones

#### Prompt 1 – Cliente de clima

> Necesito un script en Python 3 que consulte el clima de una ciudad con la librería requests usando la API de OpenWeatherMap. Debe devolver temperatura, humedad y descripción del estado del tiempo en un diccionario. Contexto: es parte de un sistema de gestión de proyectos de una empresa (EcoTech Solutions). Explica el código.

**Qué generó:** la función `obtener_clima(ciudad, api_key)`: valida que la ciudad no esté vacía, lee la clave desde `OPENWEATHER_API_KEY`, hace `requests.get` con `timeout=10` y `params=`, y según `status_code` devuelve un diccionario (200) o lanza una excepción (401, 404, otros).

**Lo que está bien (se conserva):** clave en variable de entorno, uso de `params=` en vez de concatenar la URL, `timeout`, `units=metric`/`lang=es`, no mostrar trazas.

**Problemas detectados**

| # | Problema | Decisión |
|---|---|---|
| 1.1 | La "validación" solo comprueba que no esté vacío, pero la explicación afirma que "previene inyecciones". Cualquier carácter llega a la consulta. | Reemplazada por `validar_ciudad` (lista blanca con `fullmatch`, largo 2–60). |
| 1.2 | Usa excepciones con significado incorrecto: `FileNotFoundError` para un 404, `PermissionError` para un 401 y `Exception` genérica para el resto; además el ejemplo captura `Exception`. | Jerarquía propia en `errores.py` (`ErrorNoEncontrado`, `ErrorAutenticacionAPI`, …). |
| 1.3 | `except RequestException` también captura `requests.exceptions.JSONDecodeError` (hereda de `RequestException`). Verificado: un JSON inválido se reporta como "fallo de conexión". | JSON inválido pasa a `ErrorRespuestaInvalida`, separado de los errores de red. |
| 1.4 | `raise ... from None` borra la causa y no hay `logging`: no queda rastro técnico para diagnosticar. | Se registra tipo y detalle en `app.log` (con la clave enmascarada) y se lanza sin exponerlo. |
| 1.5 | Los campos del JSON (`data["main"]["temp"]`) se leen sin proteger: si falta uno, ocurre `KeyError`. | `try/except (KeyError, IndexError, TypeError, ValueError)` + verificación de rangos. |
| 1.6 | La función mezcla validación, red, parseo y reglas de error en un solo bloque. | Separada en `_solicitar_json` (red/HTTP/JSON) y `obtener_clima` (extracción). |

#### Prompt 2 – Tipo de cambio

> Ahora una función en Python con requests que consulte el valor del dólar y del euro en CLP usando la API mindicador.cl y devuelva solo el valor y la fecha. Incluye una función que convierta un monto en USD a CLP.

**Qué generó:** `consultar_indicador(tipo)` (lista blanca `dolar`/`euro`, lee `serie[0]` con `valor` y `fecha`) y `convertir_usd_a_clp(monto)` que multiplica por el valor del día.

**Lo que está bien:** lista blanca del indicador antes de armar la URL, `serie[0]` como valor más reciente (confirmado en la documentación pública: la serie viene con la fecha más reciente primero), fecha recortada a `YYYY-MM-DD`.

**Problemas detectados**

| # | Problema | Decisión |
|---|---|---|
| 2.1 | Rama alternativa `data.get("valor")` puede devolver `None`; luego `monto * None` genera `TypeError`. | Se elimina la rama (la API entrega `serie`); si falta, `ErrorRespuestaInvalida`. |
| 2.2 | Dinero con `float` (errores de redondeo) y el valor de la API no se verifica (tipo, > 0). | Se usa `Decimal`, se comprueba `is_finite()` y `> 0`, y que la fecha tenga formato válido. |
| 2.3 | `convertir_usd_a_clp` no valida el tipo del monto (un texto produce `TypeError`) ni acepta otras monedas. | `negocio.convertir_a_clp(monto, valor)` es una función pura sobre `Decimal`; el monto lo valida `validar_monto`. |
| 2.4 | `raise Exception(...)` genérica para errores HTTP y sin registro técnico. | Excepciones específicas y `logging`. |
| 2.5 | No hay reintentos ante caídas momentáneas del servicio. | `Session` con 1 reintento automático para 500/502/503/504. |

#### Prompt 3 – Registro e inicio de sesión

> Crea un sistema de registro e inicio de sesión por consola en Python. Los usuarios se guardan en un archivo JSON local. Debe ser seguro para una evaluación universitaria de programación segura.

**Qué generó:** módulo con `generar_hash_password` (PBKDF2-HMAC-SHA256, 100.000 iteraciones, salt de 16 bytes), `cargar/guardar_usuarios`, registro, login con `compare_digest` y mensaje genérico "Credenciales inválidas".

**Lo que está bien:** hash con salt único, `secrets` para el salt, comparación en tiempo constante, mismo mensaje para usuario inexistente o clave incorrecta, uso de JSON local.

**Problemas detectados**

| # | Problema | Decisión |
|---|---|---|
| 3.1 | `validar_entrada_usuario` retorna `isalnum() or '_' in usuario`. Verificado: acepta `a!b@c_`, `ab c_` y `x'; DROP--_` (basta con un guion bajo) y `isalnum()` admite letras Unicode. | Regex `[A-Za-z0-9_]{4,20}` con `fullmatch`. |
| 3.2 | La contraseña se lee con `input()`: **se ve en pantalla** al escribirla. | `getpass.getpass`, con confirmación al registrar. |
| 3.3 | 100.000 iteraciones quedan por debajo de la recomendación actual de OWASP para PBKDF2-SHA256 (600.000). | 600.000 iteraciones, guardadas en el registro de cada usuario para poder subirlas después. |
| 3.4 | Si el usuario no existe se responde de inmediato, sin calcular el hash: la diferencia de tiempo permite enumerar usuarios, contradiciendo su propia justificación. | Se calcula un hash de relleno antes de responder. |
| 3.5 | No hay límite de intentos (fuerza bruta). | Bloqueo de 60 s tras 3 fallos, guardado en el registro del usuario. Un primer diseño mostraba solo "Credenciales inválidas" durante el bloqueo; en la prueba manual se vio que el usuario no entendía qué pasaba, así que ahora se informa el tiempo restante y el bloqueo se aplica también a usuarios inexistentes (para no revelar quién existe). |
| 3.6 | Si `usuarios.json` está corrupto, `cargar_usuarios` devuelve `{}`; el siguiente registro **sobrescribe y borra todos los usuarios**. | Ahora lanza `ErrorAlmacenamiento` y no escribe nada. |
| 3.7 | Escritura directa del archivo (puede quedar a medias) y con permisos por defecto. | Escritura atómica (`.tmp` + `os.replace`) y `chmod 600`. |
| 3.8 | `iniciar_sesion` solo imprime el resultado: no entrega un estado de sesión que el resto del sistema pueda usar. | `autenticar` devuelve el usuario; `main.py` guarda la sesión. |
| 3.9 | Política de contraseña: solo largo mínimo 8. Typo en el menú ("Serrando"). `except Exception` genérico sin registro. | Política en `validar_password`; texto corregido; excepciones específicas + registro. |

#### Prompt 4 – Funciones de validación

> Crea funciones de validación en Python para: nombre de usuario, contraseña, ciudad, código de moneda (USD, EUR, etc.) y monto numérico.

**Qué generó:** `validar_usuario`, `validar_password`, `validar_ciudad`, `validar_codigo_moneda` y `validar_monto`, con expresiones regulares y `try/except` para el monto.

**Lo que está bien:** enfoque de listas blancas con regex, política de contraseña con mayúscula, minúscula, número y símbolo, uso de `isinstance`.

**Problemas detectados (verificados ejecutando casos)**

| # | Problema | Decisión |
|---|---|---|
| 4.1 | `validar_monto` acepta `"nan"`, `"inf"` y `"1e308"` (`float("nan") < 0` es falso) y no tiene máximo. Un monto infinito se propagaría al cálculo del pago. | Regex numérica estricta (solo dígitos y hasta 2 decimales), tope de 1.000.000, retorno en `Decimal`. |
| 4.2 | `validar_ciudad` acepta `"---"` y `\s` admite tabulaciones y saltos de línea; no admite `ü`. | Nueva regex: letras, con separadores (espacio, guion, apóstrofe) solo entre letras; espacios colapsados antes de validar. |
| 4.3 | `validar_codigo_moneda` acepta cualquier código de 3 letras (`XYZ`), aunque la API solo soporta USD y EUR. | Lista blanca `MONEDAS` (única fuente de verdad en `config.py`). |
| 4.4 | Devuelven `bool` y validan `.strip()`, pero el llamador sigue usando el valor sin limpiar. | Cada validador **devuelve el valor saneado** o lanza `ErrorValidacion`. |
| 4.5 | `validar_password` valida pero ninguna parte del sistema la usa (el menú del Prompt 5 reimplementa una validación más débil). | `main.py` usa todos los validadores. |

#### Prompt 5 – Menú con control de acceso

> Crea un menú por consola que solo permita usar las consultas de clima y tipo de cambio si el usuario inició sesión.

**Qué generó:** un `main.py` único con la variable `usuario_actual` y un `if usuario_actual is None` en las opciones 3 y 4, que bloquea el acceso si no hay sesión.

**Lo que está bien:** la idea de estado de sesión y el cierre de sesión; el menú muestra el estado.

**Problemas detectados**

| # | Problema | Decisión |
|---|---|---|
| 5.1 | `import json` está solo dentro de `if __name__ == "__main__"` y `hashlib`/`secrets` dentro de funciones: el código solo funciona por casualidad y falla si se importa como módulo (`NameError`). | Imports al inicio de cada módulo. |
| 5.2 | Duplica la lógica de autenticación y deja de usar `validaciones.py`; todo en un archivo. | Proyecto modular (`auth`, `validators`, `api_clients`, …). |
| 5.3 | Las funciones de consulta se llaman sin `try/except` y solo capturan `RequestException`: un `KeyError` (campo ausente en el JSON) **cierra el programa**. | Excepciones propias capturadas en el bucle del menú. |
| 5.4 | El control de acceso es un `if` repetido en cada opción: olvidar uno deja una brecha. | `_exigir_sesion()` centralizado, llamado al inicio de cada función protegida; el estado es atributo privado de una clase. |
| 5.5 | `guardar_usuarios` hace `pass` ante `IOError` y luego se imprime "[ÉXITO] registrado": informa un éxito falso. | El error de escritura se propaga como `ErrorAlmacenamiento`. |
| 5.6 | No integra el cálculo de pagos en USD/EUR (requerimiento del enunciado) ni usa el clima para decisiones. | Opción 5 (pago en CLP) y alertas operativas por clima. |

#### Prompt 6 – Manejo de errores

> Agrega manejo de errores a las funciones de consulta de API: timeout, fallos de conexión, códigos HTTP 401, 404, 429 y 500, y JSON inválido. El programa no debe cerrarse.

**Qué generó:** `manejar_respuesta_http` (imprime un mensaje por código y decodifica el JSON) y versiones de `consultar_clima` y `consultar_tipo_cambio` con `except Timeout`, `except ConnectionError` y `except RequestException`.

**Lo que está bien:** separa `Timeout` de `ConnectionError`, contempla 401/404/429/5xx, protege `response.json()` y el acceso a claves, no imprime el objeto de la excepción.

**Problemas detectados**

| # | Problema | Decisión |
|---|---|---|
| 6.1 | Las funciones **imprimen** los errores dentro de la lógica de negocio: no se pueden reutilizar ni probar. | La capa de API lanza excepciones; solo `main.py` muestra mensajes. |
| 6.2 | No hay `logging`: el detalle técnico se pierde, justo lo que sirve para diagnosticar. | `app.log` con detalle técnico y claves enmascaradas. |
| 6.3 | `except RequestException` final sin registrar y sin distinguir el caso. | Registro + `ErrorServicioExterno`. |
| 6.4 | No cubre el 403 y no hay reintentos para fallas transitorias. | 401/403 juntos; 1 reintento automático en 5xx y errores de conexión. |
| 6.5 | `item['valor']` no se valida (tipo ni rango). | Verificación de `Decimal` finito y positivo. |
| 6.6 | Riesgo que surge al **registrar** errores: los mensajes de `requests` incluyen la URL completa con `appid=<clave>`; escribirlos al log filtraría la clave. | `ocultar_secretos()` enmascara `appid=` y el valor exacto de la clave antes de escribir. Cubierto por una prueba. |

#### Prompt 7 – Revisión y refactorización (Claude)

> puedes hacer un readme.md explicando éstos inputs, mandarme el código cómo deberia verse completo y revisar si hay algo que falla?

**Qué se hizo:** con los seis prompts y respuestas de Gemini se revisó el código contra la guía y la rúbrica, se ejecutaron casos de prueba para confirmar los problemas (tablas anteriores) y se rehízo el proyecto como módulos. Después se escribieron las pruebas automáticas y se ejecutaron (22 pruebas, todas OK, con respuestas de API simuladas).

### 6.3 Qué se usó, qué se modificó y qué se descartó

| Parte | Origen | Decisión |
|---|---|---|
| Uso de `requests`, `params=`, `timeout`, clave por variable de entorno | Gemini | **Se mantuvo** |
| Hash PBKDF2 + salt + `compare_digest` + mensaje genérico | Gemini | **Se mantuvo**, subiendo iteraciones y agregando bloqueo y hash de relleno |
| Lista blanca de indicadores, `serie[0]`, recorte de fecha | Gemini | **Se mantuvo** (centralizada en `MONEDAS`) |
| `except Timeout` / `ConnectionError` separados, códigos 401/404/429/5xx | Gemini | **Se mantuvo**, pero lanzando excepciones propias en vez de imprimir |
| Validadores (`validar_monto`, `validar_ciudad`, `validar_codigo_moneda`, usuario) | Gemini | **Modificados**: aceptaban `nan`, `inf`, `---`, `XYZ`, `a!b@c_` |
| Menú con `if usuario_actual is None` repetido | Gemini | **Modificado**: control centralizado en `_exigir_sesion()` |
| Rama `data.get("valor")`, `raise Exception(...)`, `FileNotFoundError` para 404, `pass` ante error de escritura, `input()` para la contraseña, `return {}` ante archivo corrupto | Gemini | **Descartado** |
| Jerarquía de excepciones, logging con enmascarado, `Decimal`, reintentos, alertas de clima, cálculo de pagos, pruebas | Refactorización | **Agregado** |

---

## 7. Pruebas

**Automáticas** (`python3 -m unittest -v`): 22 pruebas sin internet. Cubren validadores con entradas maliciosas, hash y bloqueo, archivo corrupto, códigos HTTP, timeout, JSON inválido, campos faltantes, valores fuera de rango, ausencia de la clave en el log, control de sesión y un flujo completo del menú.

**Manuales** (con internet y clave real; completar con lo observado):

| # | Prueba | Resultado esperado | Resultado obtenido |
|---|---|---|---|
| 1 | Opción 3 sin iniciar sesión | "Acceso denegado" | ![image-20261115174143814](/image-20261115174143814.png) |
| 2 | Registrar usuario con contraseña débil (`abc123`) | Rechazo con mensaje de política | ![image-20261115174203303](/image-20261115174203303.png) |
| 3 | Revisar `usuarios.json` después de registrar | Solo hash y salt, sin la contraseña | ![image-20261115174217350](/image-20261115174217350.png) |
| 4 | Login con clave incorrecta 3 veces | Mensaje con los segundos de bloqueo; luego se puede reintentar | ![image-20261115174230888](/image-20261115174230888.png) |
| 5 | Clima de `Chillán`, `CL` | Temperatura, humedad, estado | ![image-20261115174950658](/image-20261115174950658.png) |
| 6 | Ciudad `'; DROP--` | Rechazada por validación | |
| 7 | Ciudad inexistente (`Zzzzqx`) | "Verifique la ciudad o el país" | ![image-20261115175021225](/image-20261115175021225.png) |
| 8 | Clave de API incorrecta en `.env` | Mensaje de credenciales del servicio, sin la clave | ![image-20261115175038550](/image-20261115175038550.png) |
| 9 | Desconectar internet y consultar | "Revise su conexión", el menú sigue activo | ![image-20261115175152321](/image-20261115175152321.png) |
| 10 | Tipo de cambio USD y EUR | Valor en CLP con fecha | ![image-20261115175326280](/image-20261115175326280.png)![image-20261115175333880](/image-20261115175333880.png) |
| 11 | Pago de `1500` USD / monto `nan`, `-5`, `abc` | Conversión correcta / rechazos | ![image-20261115175500868](/image-20261115175500868.png)![image-20261115175429194](/image-20261115175429194.png) |
|      |                                                   |                                                              |  |

## 8. Limitaciones

- El bloqueo por intentos es por usuario y se guarda en el JSON; un atacante podría bloquear temporalmente a un usuario. Para un sistema real se usarían una base de datos y límites por IP/dispositivo.
- `usuarios.json` es un almacenamiento simple para fines académicos; el registro de usuarios está abierto a cualquiera que ejecute el programa.
- Los datos de las APIs se muestran en consola sin persistirse; una mejora posible es guardar un historial local de consultas.
- La consulta por nombre de ciudad de OpenWeatherMap puede ser ambigua (varias ciudades con el mismo nombre); por eso se admite el código de país opcional.
