"""Enlaza fuentes existentes del cálculo comercial; solo lectura, sin otro motor."""
import hashlib
import json
from datetime import timezone
from decimal import Decimal, InvalidOperation

from services.fechas import ahora_utc_naive
from services.costos_productos import preparar_detalles
from services.motor_costeo_productos import huella_detalles
from services.composicion_costo_producto import construir_detalles, construir_detalles_combo
from services.reglas_economicas import calcular_pisos_regla, resolver_regla_vigente, clave_alcance
from services.motor_comercial_canal import calcular_precio_minimo_canal


def _fecha(valor):
    if valor is not None and valor.tzinfo is not None:
        return valor.astimezone(timezone.utc).replace(tzinfo=None)
    return valor


def _vigencia(registro, ahora):
    desde = _fecha(registro.vigente_desde)
    hasta = _fecha(registro.vigente_hasta)
    if (not registro.vigente or registro.estado != 'vigente' or desde is None
            or desde > ahora or (hasta is not None and hasta <= ahora)):
        raise ValueError('La versión no está vigente en la fecha del cálculo.')


def _contexto(registro, organizacion_id, unidad_negocio_id):
    if registro.organizacion_id != organizacion_id or registro.unidad_negocio_id != unidad_negocio_id:
        raise ValueError('La fuente no pertenece a la organización y unidad activas.')


def _entero(valor):
    if isinstance(valor, bool): raise ValueError('Importe no válido.')
    try: numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError('Importe no válido.') from error
    if not numero.is_finite() or numero != numero.to_integral_value() or not 0 <= numero <= 10**15:
        raise ValueError('Importe no válido.')
    return int(numero)


def _validar_costo(costo, perfil, modelo_costo, ahora):
    _vigencia(costo, ahora)
    if costo.moneda != 'ARS': raise ValueError('El cálculo requiere una versión de costo en ARS.')
    if perfil is None or not perfil.activo or perfil.tipo not in {'simple','produccion','combo'}:
        raise ValueError('Falta un perfil de costeo activo y único para el producto.')
    if (perfil.organizacion_id,perfil.unidad_negocio_id,perfil.producto_id) != (costo.organizacion_id,costo.unidad_negocio_id,costo.producto_id):
        raise ValueError('El perfil y la versión de costo no corresponden al mismo producto y contexto.')
    if not costo.detalles: raise ValueError('La versión de costo no tiene composición verificable.')
    preparados = preparar_detalles([{
        k:getattr(d,k,None) for k in ('tipo','codigo','concepto','cantidad','unidad_medida',
            'costo_unitario_centavos','porcentaje_merma','orden','observacion')
    } for d in costo.detalles])
    if (sum(d['subtotal_centavos'] for d in preparados) != _entero(costo.costo_total_centavos)
            or any(_entero(d.subtotal_centavos) != p['subtotal_centavos'] for d,p in zip(costo.detalles,preparados))):
        raise ValueError('La composición no reproduce el total de la versión de costo.')
    if perfil.tipo == 'simple':
        if costo.tipo != 'manual': raise ValueError('El perfil simple requiere un costo manual.')
    else:
        actuales = construir_detalles_combo(perfil,CostoProductoVersion=modelo_costo) if perfil.tipo == 'combo' else construir_detalles(perfil)
        if costo.tipo != 'calculado' or huella_detalles(preparar_detalles(actuales)) != huella_detalles(costo.detalles):
            raise ValueError('La ficha o sus fuentes cambiaron; recalculá y aprobá el costo antes de usarlo.')
    return huella_detalles(costo.detalles)


def _validar_tramos(regla):
    tramos = sorted(regla.tramos,key=lambda t:t.precio_desde_centavos)
    siguiente = 0
    if not tramos: raise ValueError('Falta declarar la cobertura de cargos fijos, incluido el cargo cero.')
    for tramo in tramos:
        desde = _entero(tramo.precio_desde_centavos)
        hasta = None if tramo.precio_hasta_centavos is None else _entero(tramo.precio_hasta_centavos)
        _entero(tramo.cargo_fijo_centavos)
        if siguiente is None or desde != siguiente or (hasta is not None and hasta <= desde):
            raise ValueError('Los tramos deben cubrir todos los precios sin huecos ni superposiciones; declará también el cargo cero.')
        siguiente = hasta
    if siguiente is not None:
        raise ValueError('La cobertura de cargos debe terminar en un tramo sin límite, incluso si su cargo es cero.')


def _datos(registro, campos):
    return {campo: (format(valor,'f') if isinstance(valor,Decimal) else _fecha(valor).isoformat() if hasattr(valor,'isoformat') else valor)
        for campo in campos for valor in [getattr(registro,campo)]}


def construir_enlaces(*, organizacion_id, unidad_negocio_id, costos, inclusiones,
                       reglas_economicas, reglas_canal, perfiles, modelo_costo, ahora=None):
    """Devuelve las filas usadas por la bandeja existente y bloqueos visibles."""
    ahora = _fecha(ahora or ahora_utc_naive())
    pisos, simulaciones, bloqueos = [], [], []
    costos = list(costos); reglas_canal = list(reglas_canal)
    def bloquear(costo, motivo, regla=None):
        bloqueos.append({'producto_id':costo.producto_id,'sku':costo.producto.sku,
            'costo_version_id':costo.id,'lista_id':getattr(regla,'lista_precio_id',None),'motivo':str(motivo)})
    for costo in sorted((c for c in costos if c.vigente),key=lambda c:c.id):
        try:
            _contexto(costo,organizacion_id,unidad_negocio_id)
            duplicados = [c for c in costos if c.vigente and (c.producto_id,c.moneda,c.organizacion_id,c.unidad_negocio_id)==(costo.producto_id,costo.moneda,organizacion_id,unidad_negocio_id)]
            if len(duplicados)!=1: raise ValueError('Hay más de una versión de costo vigente para el mismo producto y moneda.')
            candidatas = [i for i in inclusiones if i.producto_id==costo.producto_id and i.activo]
            if len(candidatas)!=1: raise ValueError('Se requiere una inclusión activa de catálogo inequívoca; no se elige la primera.')
            inclusion = candidatas[0]
            _contexto(inclusion.catalogo,organizacion_id,unidad_negocio_id)
            if inclusion.producto.organizacion_id != organizacion_id or not inclusion.activo:
                raise ValueError('El producto de catálogo debe pertenecer al tenant y estar activo.')
            candidatos_perfil = [p for p in perfiles if (p.producto_id,p.organizacion_id,p.unidad_negocio_id)==(costo.producto_id,organizacion_id,unidad_negocio_id)]
            perfil = candidatos_perfil[0] if len(candidatos_perfil)==1 else None
            composicion = _validar_costo(costo,perfil,modelo_costo,ahora)
            reglas = [r for r in reglas_economicas if r.organizacion_id==organizacion_id and r.unidad_negocio_id in (None,unidad_negocio_id)]
            regla = resolver_regla_vigente(reglas,unidad_negocio_id=unidad_negocio_id,catalogo_id=inclusion.catalogo_id,producto_id=costo.producto_id)
            if regla is None: raise ValueError('Falta una regla económica aplicable y vigente.')
            if sum(r.vigente and r.clave_alcance==regla.clave_alcance for r in reglas)!=1:
                raise ValueError('La regla económica aplicable es ambigua.')
            _vigencia(regla,ahora)
            if clave_alcance(regla.alcance,unidad_negocio_id=regla.unidad_negocio_id,catalogo_id=regla.catalogo_id,producto_id=regla.producto_id)!=regla.clave_alcance:
                raise ValueError('El alcance de la regla económica no coincide con sus referencias.')
            calculados = calcular_pisos_regla(costo.costo_total_centavos,regla)
            fila = {'costo':costo,'inclusion':inclusion,'regla':regla,'pisos':calculados}
            pisos.append(fila)
        except ValueError as error:
            bloquear(costo,error); continue
        for canal in (r for r in reglas_canal if r.vigente):
            try:
                lista = canal.lista_precio
                _contexto(lista,organizacion_id,unidad_negocio_id)
                if lista.moneda != costo.moneda: raise ValueError('La moneda de la lista no coincide con el costo.')
                if lista.estado in {'archivado','cancelado'}: raise ValueError('La lista de precios está archivada o cancelada.')
                if sum(r.vigente and r.lista_precio_id==canal.lista_precio_id for r in reglas_canal)!=1:
                    raise ValueError('La lista tiene más de una política de canal vigente.')
                _vigencia(canal,ahora);_validar_tramos(canal)
                for campo in ('comision_pct','publicidad_pct','financiacion_pct','devoluciones_pct'):
                    if getattr(canal,campo) is None:
                        raise ValueError('La política requiere porcentajes declarados, incluido cero; no se reemplazan faltantes por cero.')
                _entero(canal.umbral_envio_centavos);_entero(canal.costo_envio_default_centavos)
                minimo = calcular_precio_minimo_canal(calculados['minimo']['piso_liquidacion_centavos'],canal)
                objetivo = calcular_precio_minimo_canal(calculados['objetivo']['piso_liquidacion_centavos'],canal)
                traza = {
                    'organizacion_id':organizacion_id,'unidad_negocio_id':unidad_negocio_id,
                    'producto_id':costo.producto_id,'sku':costo.producto.sku,'perfil_id':perfil.id,
                    'catalogo_producto_id':inclusion.id,'catalogo_id':inclusion.catalogo_id,
                    'costo':_datos(costo,('id','numero_version','tipo','moneda','costo_total_centavos','vigente_desde','vigente_hasta')),
                    'huella_composicion':composicion,
                    'regla_economica':_datos(regla,('id','numero_version','clave_alcance','impuesto_pct','metodo_impuesto','utilidad_minima_pct','utilidad_objetivo_pct','metodo_utilidad','incremento_redondeo_centavos','vigente_desde','vigente_hasta')),
                    'politica_canal':_datos(canal,('id','numero_version','lista_precio_id','comision_pct','publicidad_pct','financiacion_pct','devoluciones_pct','umbral_envio_centavos','costo_envio_default_centavos','incremento_redondeo_centavos','vigente_desde','vigente_hasta')),
                    'canal':lista.tipo,'moneda':lista.moneda,
                    'tramos':[_datos(t,('precio_desde_centavos','precio_hasta_centavos','cargo_fijo_centavos')) for t in sorted(canal.tramos,key=lambda t:t.precio_desde_centavos)],
                    'minimo':minimo,'objetivo':objetivo,
                    'alcance':'estimacion_segun_versiones_internas',
                    'embalaje_verificado':False,'cargos_contrastados_cuenta':False,
                    'faltantes':['Verificar si el embalaje integra la composición de costo; no se suma otro importe automáticamente.',
                        'Contrastar cargos, promociones y envío con la cuenta y publicación exactas.'],
                    'habilita_publicacion':False,'conexiones_externas':0,
                }
                huella = hashlib.sha256(json.dumps(traza,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                simulaciones.append({**fila,'regla_canal':canal,'minimo':minimo,'objetivo':objetivo,
                    'trazabilidad_economica':{**traza,'huella_enlace':huella}})
            except ValueError as error:
                bloquear(costo,error,canal)
    return pisos,simulaciones,bloqueos
