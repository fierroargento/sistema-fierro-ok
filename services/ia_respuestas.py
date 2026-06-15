def ia_etiqueta_faltante_service(campo):
    mapa = {
        "nombre": "Nombre",
        "apellido": "Apellido",
        "dni": "DNI",
        "telefono": "Teléfono",
        "direccion": "Dirección completa",
        "localidad": "Localidad",
        "codigo_postal": "Código postal",
    }
    return mapa.get(
        str(campo or "").strip(),
        str(campo or "").replace("_", " ").capitalize(),
    )

def agregar_marca_resumen_unica_service(resumen_actual, marca, limite=1000):
    resumen = str(resumen_actual or "").strip()
    marca = str(marca or "").strip()

    if not marca:
        return resumen[:limite]

    if marca in resumen:
        return resumen[:limite]

    return f"{resumen} | {marca}".strip(" |")[:limite]
