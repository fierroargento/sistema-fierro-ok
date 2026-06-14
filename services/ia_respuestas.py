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
