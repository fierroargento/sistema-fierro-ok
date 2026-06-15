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

def detectar_contexto_resumen_faltantes_service(resumen):
    resumen = str(resumen or "").lower()

    resumen_ml_explicito = any(k in resumen for k in [
        "datos en mercado libre",
        "datos están en mercado libre",
        "datos estan en mercado libre",
        "datos ya están en mercado libre",
        "datos ya estan en mercado libre",
        "son los mismos de la compra",
        "datos de mi cuenta",
    ])

    pregunta_por_que = any(k in resumen for k in [
        "por qué",
        "por que",
        "pide explicación",
        "pide explicacion",
        "por qué pedimos",
        "por que pedimos",
        "por qué piden",
        "por que piden",
    ])

    pregunta_costo_envio = any(k in resumen for k in [
        "costo de envío",
        "costo de envio",
        "cuánto sale",
        "cuanto sale",
        "sale el envío",
        "sale el envio",
        "valor del envío",
        "valor del envio",
    ])

    pregunta_cuando_sale = any(k in resumen for k in [
        "cuándo lo envían",
        "cuando lo envian",
        "cuándo envían",
        "cuando envian",
        "cuándo lo mandan",
        "cuando lo mandan",
        "cuándo despachan",
        "cuando despachan",
        "cuando la despachan",
        "cuándo la despachan",
        "cuando la envias",
        "cuándo la envias",
        "cuando la envían",
        "cuándo la envían",
        "cuando lo envias",
        "cuándo lo envias",
        "fecha de envío",
        "fecha de envio",
        "cuando sale",
        "cuándo sale",
    ])

    pregunta_cuanto_tarda = any(k in resumen for k in [
        "cuánto tarda",
        "cuanto tarda",
        "cuánto demora",
        "cuanto demora",
        "demora",
        "tiempo de entrega",
        "cuándo llega",
        "cuando llega",
        "cuando me llega",
        "cuándo me llega",
    ])

    cliente_dice_ya_los_pase = any(k in resumen for k in [
        "ya los pasé",
        "ya los pase",
        "ya pasó",
        "ya paso",
        "ya envié",
        "ya envie",
    ])

    pide_llamada_o_whatsapp = any(k in resumen for k in [
        "llamada",
        "llamar",
        "llamame",
        "llámame",
        "hablar por whatsapp",
        "te paso mi whatsapp",
        "por whatsapp",
        "mandame whatsapp",
        "mandame un whatsapp",
    ])

    return {
        "resumen_ml_explicito": resumen_ml_explicito,
        "pregunta_por_que": pregunta_por_que,
        "pregunta_costo_envio": pregunta_costo_envio,
        "pregunta_cuando_sale": pregunta_cuando_sale,
        "pregunta_cuanto_tarda": pregunta_cuanto_tarda,
        "cliente_dice_ya_los_pase": cliente_dice_ya_los_pase,
        "pide_llamada_o_whatsapp": pide_llamada_o_whatsapp,
        "hay_contexto_especial": any([
            resumen_ml_explicito,
            pregunta_por_que,
            pregunta_costo_envio,
            pregunta_cuando_sale,
            pregunta_cuanto_tarda,
            cliente_dice_ya_los_pase,
            pide_llamada_o_whatsapp,
        ]),
    }
