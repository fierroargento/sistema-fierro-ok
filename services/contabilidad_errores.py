"""Avisos contables públicos sin detalles internos de base de datos."""


def mensaje_error_contable(error):
    if isinstance(error, ValueError):
        return str(error)
    diagnostico = getattr(getattr(error, "orig", None), "diag", None)
    restriccion = getattr(diagnostico, "constraint_name", None)
    if restriccion == "uq_asiento_borrador_clave":
        return "Este asiento borrador ya existe. No se creó un duplicado."
    if restriccion == "uq_cuenta_contable_tenant_unidad":
        return "Ya existe una cuenta con ese código en la unidad activa."
    return "No se pudo completar la operación contable. Intentá nuevamente."
