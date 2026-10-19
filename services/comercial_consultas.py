"""Consultas del panel comercial tenant."""

from services.catalogo_ficha_integral import (
    calcular_completitud,
    cargar_json,
    numero_visual,
    presentar_atributos,
    presentar_variantes,
)
from services.enlace_economico_producto import construir_enlaces
from services.cobertura_precio_publicacion import completar_cobertura
from services.control_comercial_masivo import construir_bandeja
from services.validacion_integral_canal import construir_tablero
from services.control_motores_comerciales import construir_control_motores
from services.plan_transicion_motores_comerciales import construir_plan_transicion
from services.ensayo_transicion_motores_comerciales import construir_ensayo_transicion


def obtener_datos_panel_comercial(organizacion_id, unidad_negocio_id, *, modelos):
    Unidad = modelos["UnidadNegocio"]
    Producto = modelos["Producto"]
    Catalogo = modelos["Catalogo"]
    CatalogoProducto = modelos["CatalogoProducto"]
    Costo = modelos["CostoProductoVersion"]
    Lista = modelos["ListaPrecio"]
    Politica = modelos["PoliticaComercialLista"]
    Item = modelos["ListaPrecioItem"]
    ReglaEconomica = modelos["ReglaEconomicaVersion"]
    ReglaCanal = modelos["ReglaCanalVersion"]
    Promocion = modelos["PromocionCanalObservacion"]
    Propuesta = modelos["PropuestaAccionComercial"]
    ObservacionCanal = modelos["ObservacionComercialCanal"]
    ReglaValidacion = modelos["ReglaValidacionCanalVersion"]
    inclusiones = CatalogoProducto.query.join(
        Catalogo
    ).filter(
        Catalogo.organizacion_id == organizacion_id
        , Catalogo.unidad_negocio_id == unidad_negocio_id
    ).order_by(CatalogoProducto.nombre_comercial).all()
    for inclusion in inclusiones:
        porcentaje, faltantes = calcular_completitud(
            inclusion, inclusion.producto
        )
        inclusion.completitud_visual = porcentaje
        inclusion.faltantes_visual = ", ".join(faltantes) or None
    costos = Costo.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id
    ).order_by(Costo.fecha_creacion.desc()).all()
    reglas_economicas = ReglaEconomica.query.filter(
        ReglaEconomica.organizacion_id == organizacion_id,
        (ReglaEconomica.unidad_negocio_id.is_(None))
        | (ReglaEconomica.unidad_negocio_id == unidad_negocio_id),
    ).order_by(ReglaEconomica.fecha_creacion.desc()).all()
    reglas_canal = ReglaCanal.query.join(Lista).filter(
        Lista.organizacion_id == organizacion_id,
        Lista.unidad_negocio_id == unidad_negocio_id,
    ).order_by(ReglaCanal.fecha_creacion.desc()).all()
    perfiles_costeo = modelos["PerfilCosteoProducto"].query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    ).all()
    pisos_economicos, simulaciones_canal, bloqueos_enlace_economico = construir_enlaces(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        costos=costos, inclusiones=inclusiones, reglas_economicas=reglas_economicas,
        reglas_canal=reglas_canal, perfiles=perfiles_costeo, modelo_costo=Costo,
    )
    items = Item.query.join(Lista).filter(
        Lista.organizacion_id == organizacion_id,
        Lista.unidad_negocio_id == unidad_negocio_id,
    ).order_by(Item.fecha_creacion.desc()).all()
    promociones = Promocion.query.join(Lista).filter(
        Lista.organizacion_id == organizacion_id,
        Lista.unidad_negocio_id == unidad_negocio_id,
    ).order_by(Promocion.fecha_observacion.desc()).all()
    observaciones_canal = ObservacionCanal.query.join(Lista).filter(
        Lista.organizacion_id == organizacion_id,
        Lista.unidad_negocio_id == unidad_negocio_id,
    ).order_by(ObservacionCanal.fecha_observacion.desc()).all()
    propuestas_comerciales = Propuesta.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    ).order_by(Propuesta.fecha_creacion.desc()).all()
    reglas_validacion = ReglaValidacion.query.join(Lista).filter(
        Lista.organizacion_id == organizacion_id,
        Lista.unidad_negocio_id == unidad_negocio_id,
    ).order_by(ReglaValidacion.fecha_creacion.desc()).all()
    simulaciones_canal = [completar_cobertura(fila,
        observaciones=observaciones_canal, reglas_validacion=reglas_validacion)
        for fila in simulaciones_canal]
    control_comercial, resumen_control_comercial = construir_bandeja(
        simulaciones_canal, items, promociones, observaciones_canal,
    )
    tablero_preparacion, resumen_preparacion, propuestas_obsoletas = construir_tablero(
        control_comercial, reglas_validacion, observaciones_canal,
        promociones, propuestas_comerciales,
    )
    propuestas_comerciales.sort(key=lambda p: (p.id in propuestas_obsoletas, -(p.depende_de.id if p.depende_de is not None else p.id), p.orden, p.id))
    listas = Lista.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id
    ).order_by(Lista.nombre).all()
    politicas = Politica.query.join(Lista).filter(
        Lista.organizacion_id == organizacion_id,
        Lista.unidad_negocio_id == unidad_negocio_id,
    ).order_by(Politica.fecha_creacion.desc()).all()
    control_motores = construir_control_motores(listas, politicas, reglas_canal, items)
    plan_transicion_motores = construir_plan_transicion(control_motores)
    ensayo_transicion_motores = construir_ensayo_transicion(
        listas, politicas, reglas_canal, items,
    )
    return {
        "productos_maestro": Producto.query.filter_by(
            organizacion_id=organizacion_id
        ).order_by(
            Producto.sku.asc()
        ).all(),
        "catalogos": Catalogo.query.filter_by(
            organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id
        ).order_by(Catalogo.nombre.asc()).all(),
        "inclusiones": inclusiones,
        "productos_relacionables": inclusiones,
        "catalogo_json": cargar_json,
        "catalogo_numero": numero_visual,
        "presentar_atributos": presentar_atributos,
        "presentar_variantes": presentar_variantes,
        "inclusiones_preparatorias": inclusiones,
        "inclusiones_activas": [
            inclusion for inclusion in inclusiones if inclusion.activo
        ],
        "costos": costos,
        "listas": listas,
        "politicas": politicas,
        "items": items,
        "reglas_economicas": reglas_economicas,
        "pisos_economicos": pisos_economicos,
        "reglas_canal": reglas_canal,
        "simulaciones_canal": simulaciones_canal,
        "bloqueos_enlace_economico": bloqueos_enlace_economico,
        "control_comercial": control_comercial,
        "resumen_control_comercial": resumen_control_comercial,
        "promociones_canal": promociones,
        "propuestas_comerciales": propuestas_comerciales,
        "observaciones_comerciales_canal": observaciones_canal,
        "reglas_validacion_canal": reglas_validacion,
        "tablero_preparacion": tablero_preparacion,
        "resumen_preparacion": resumen_preparacion,
        "propuestas_obsoletas": propuestas_obsoletas,
        "control_motores": control_motores,
        "plan_transicion_motores": plan_transicion_motores,
        "ensayo_transicion_motores": ensayo_transicion_motores,
    }
