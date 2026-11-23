"""Reglas de negocio de EcoTech: pagos en moneda extranjera y alertas de clima."""
from decimal import ROUND_HALF_UP, Decimal

from errores import ErrorValidacion

_PALABRAS_PRECIPITACION = ("lluvia", "llovizna", "chubasco", "tormenta", "nieve")


def convertir_a_clp(monto: Decimal, valor_en_clp: Decimal) -> Decimal:
    """Convierte un monto en moneda extranjera a CLP (usa Decimal, no float, para dinero)."""
    if monto <= 0 or valor_en_clp <= 0:
        raise ErrorValidacion("El monto y el tipo de cambio deben ser mayores que 0.")
    return (monto * valor_en_clp).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def evaluar_condiciones_proyecto(clima: dict) -> list[str]:
    """Devuelve recomendaciones operativas según el clima (lista vacía = sin alertas)."""
    alertas = []
    descripcion = clima["descripcion"].lower()
    if any(palabra in descripcion for palabra in _PALABRAS_PRECIPITACION):
        alertas.append("Precipitaciones previstas: evalúe reprogramar actividades al aire libre.")
    if clima["temperatura"] >= 35:
        alertas.append("Calor extremo: limite el trabajo a la intemperie en horas de mayor temperatura.")
    if clima["temperatura"] <= 0:
        alertas.append("Riesgo de heladas: revise equipos y seguridad del personal en terreno.")
    if clima["humedad"] >= 90:
        alertas.append("Humedad muy alta: puede afectar equipos eléctricos y electrónicos.")
    return alertas
