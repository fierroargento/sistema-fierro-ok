"""Control integral de la estructura empresarial del tenant, de solo lectura."""

import hashlib
import io
import json


def controlar_estructura(*, organizacion, datos):
    organizacion_id = organizacion.id
    nombres = ("unidades", "sucursales", "entidades_fiscales", "catalogos", "productos", "modulos", "vinculos_canales")
    colecciones = {
        nombre: [x for x in datos.get(nombre, []) if x.organizacion_id == organizacion_id]
        for nombre in nombres
    }
    hallazgos = []

    def agregar(codigo, entidad, identificador, detalle):
        hallazgos.append({"codigo": codigo, "entidad": entidad, "id": identificador, "detalle": detalle})

    def validar_codigos(nombre):
        vistos = set()
        for registro in colecciones[nombre]:
            codigo = str(getattr(registro, "codigo", "") or "").strip().lower()
            if not codigo or codigo in vistos:
                agregar("codigo_duplicado", nombre, registro.id, "El código está vacío o repetido dentro del tenant.")
            vistos.add(codigo)

    for nombre in ("unidades", "sucursales", "entidades_fiscales", "catalogos", "modulos"):
        validar_codigos(nombre)
    unidad_ids = {x.id for x in colecciones["unidades"]}
    sucursal_ids = {x.id for x in colecciones["sucursales"]}
    entidad_ids = {x.id for x in colecciones["entidades_fiscales"]}
    catalogo_ids = {x.id for x in colecciones["catalogos"]}

    principales = [x for x in colecciones["sucursales"] if getattr(x, "es_principal", False) and getattr(x, "activa", False)]
    activas = [x for x in colecciones["sucursales"] if getattr(x, "activa", False)]
    if activas and len(principales) != 1:
        agregar("sucursal_principal_invalida", "sucursales", None, "Debe existir exactamente una sucursal principal activa.")
    for catalogo in colecciones["catalogos"]:
        if catalogo.unidad_negocio_id is not None and catalogo.unidad_negocio_id not in unidad_ids:
            agregar("catalogo_unidad_ajena", "catalogo", catalogo.id, "La unidad del catálogo no pertenece al tenant.")
    cuits = set()
    for entidad in colecciones["entidades_fiscales"]:
        cuit = "".join(c for c in str(getattr(entidad, "cuit", "") or "") if c.isdigit())
        if cuit and (len(cuit) != 11 or cuit in cuits):
            agregar("cuit_invalido_o_duplicado", "entidad_fiscal", entidad.id, "El CUIT es inválido o está repetido.")
        if cuit:
            cuits.add(cuit)
        if getattr(entidad, "facturacion_habilitada", False) and not getattr(entidad, "activa", False):
            agregar("facturacion_sobre_entidad_inactiva", "entidad_fiscal", entidad.id, "La entidad factura aunque está inactiva.")

    cuentas = set()
    for vinculo in colecciones["vinculos_canales"]:
        if vinculo.unidad_negocio_id not in unidad_ids:
            agregar("vinculo_unidad_ajena", "vinculo", vinculo.id, "La unidad no pertenece al tenant.")
        for campo, ids, codigo in (("catalogo_id", catalogo_ids, "vinculo_catalogo_ajeno"), ("sucursal_operativa_id", sucursal_ids, "vinculo_sucursal_ajena"), ("entidad_fiscal_id", entidad_ids, "vinculo_entidad_ajena")):
            valor = getattr(vinculo, campo, None)
            if valor is not None and valor not in ids:
                agregar(codigo, "vinculo", vinculo.id, "La relación estructural no pertenece al tenant.")
        identidades = [
            ("mercado_libre", getattr(vinculo, "mercado_libre_cuenta_id", None)),
            ("tienda_nube", getattr(vinculo, "tienda_nube_cuenta_id", None)),
            ("whatsapp", getattr(vinculo, "whatsapp_phone_number_id", None)),
        ]
        presentes = [(tipo, valor) for tipo, valor in identidades if valor not in (None, "")]
        if len(presentes) != 1:
            agregar("cuenta_canal_ambigua", "vinculo", vinculo.id, "El vínculo debe resolver exactamente una cuenta externa.")
        for clave in presentes:
            if clave in cuentas:
                agregar("cuenta_canal_duplicada", "vinculo", vinculo.id, "La cuenta externa aparece en más de un vínculo.")
            cuentas.add(clave)

    estados = {"desactivado", "prueba", "activo"}
    for modulo in colecciones["modulos"]:
        if modulo.estado not in estados:
            agregar("estado_modulo_invalido", "modulo", modulo.id, "El estado del módulo no pertenece al contrato SaaS.")
    if not colecciones["unidades"]:
        agregar("tenant_sin_unidades", "organizacion", organizacion_id, "La organización no tiene unidades de negocio.")
    if getattr(organizacion, "activa", False) and not any(getattr(x, "activa", False) for x in colecciones["unidades"]):
        agregar("tenant_activo_sin_unidad", "organizacion", organizacion_id, "La organización activa no tiene una unidad activa.")

    resumen = {nombre: len(valor) for nombre, valor in colecciones.items()}
    resumen.update({"sucursales_principales_activas": len(principales), "hallazgos": len(hallazgos)})
    resultado = {
        "organizacion_id": organizacion_id,
        "organizacion_activa": bool(getattr(organizacion, "activa", False)),
        "modo": "solo_lectura",
        "aprobado": not hallazgos,
        "resumen": resumen,
        "hallazgos": hallazgos,
        "controles": {"aislamiento_tenant": True, "modulos_activados": 0, "cuentas_conectadas": 0, "pedidos_modificados": 0, "facturas_emitidas": 0, "escrituras": 0, "acciones_externas": 0},
    }
    resultado["huella_control"] = hashlib.sha256(json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return resultado


def exportar_control(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
