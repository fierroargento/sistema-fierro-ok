"""Evidencia local versionada de embalaje e identidad declarada de publicación."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json

from services.fechas import ahora_utc_naive
from services.motor_comercial_canal import calcular_precio_minimo_canal

CLAVE = '_coberturas_economicas'
MAX_VERSIONES = 100


def _json(inclusion):
    try:
        datos=json.loads(inclusion.canales_json or '{}')
        if not isinstance(datos,dict):raise ValueError()
        historial=datos.get(CLAVE,[])
        if not isinstance(historial,list) or len(historial)>MAX_VERSIONES or any(not isinstance(v,dict) for v in historial):raise ValueError()
        return datos,historial
    except (ValueError,TypeError) as error:
        raise ValueError('La evidencia del producto está dañada; requiere revisión sin sobrescribirla.') from error


def preservar_coberturas(inclusion, canales):
    datos,historial=_json(inclusion)
    return {**canales,**({CLAVE:historial} if CLAVE in datos else {})}


def _texto(valor,nombre,limite):
    texto=str(valor or '').strip()
    if not texto or len(texto)>limite:raise ValueError(f'Completá {nombre}, hasta {limite} caracteres.')
    return texto


def _huella(datos):
    return sha256(json.dumps(datos,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _importe(valor):
    if isinstance(valor,bool) or not isinstance(valor,int) or not 0<=valor<=10**15:
        raise ValueError('El embalaje debe expresarse en centavos enteros no negativos.')
    return valor


def guardar_cobertura(fila, *, cuenta, publicacion, variante, modo_embalaje, detalle_ids,
                     adicional_centavos, referencia, huella_esperada, usuario, db_session, ahora=None):
    """El llamador bloquea la inclusión; se verifica el origen y se agrega historia."""
    traza=fila['trazabilidad_economica'];inclusion=fila['inclusion']
    base=traza.get('huella_base',traza['huella_enlace'])
    if huella_esperada!=traza['huella_enlace']:
        raise ValueError('Cambió el cálculo o su evidencia. Cerrá y volvé a abrir Gestionar.')
    datos,historial=_json(inclusion)
    if len(historial)>=MAX_VERSIONES:raise ValueError('La evidencia alcanzó su límite de versiones; no se borra historia automáticamente.')
    modo=str(modo_embalaje or '')
    if modo not in {'incluido','adicional','sin_costo'}:raise ValueError('Seleccioná cómo se registra el embalaje.')
    ids=list(detalle_ids)
    if any(type(i) is not int for i in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Las líneas de embalaje no son válidas.')
    por_id={d.id:d for d in fila['costo'].detalles}
    if any(i not in por_id for i in ids):raise ValueError('Una línea no pertenece a la versión de costo actual.')
    adicional=_importe(adicional_centavos)
    if modo=='incluido' and (not ids or adicional):raise ValueError('Seleccioná las líneas incluidas y dejá el gasto adicional en cero.')
    if modo!='incluido' and ids:raise ValueError('No selecciones líneas incluidas al declarar un gasto adicional o sin costo.')
    if modo=='adicional' and adicional<=0:raise ValueError('El embalaje adicional debe ser mayor que cero.')
    if modo=='sin_costo' and adicional:raise ValueError('Sin costo requiere un adicional de cero, declarado con referencia.')
    evidencia={
        'version':len(historial)+1,'organizacion_id':traza['organizacion_id'],'unidad_negocio_id':traza['unidad_negocio_id'],
        'catalogo_producto_id':inclusion.id,'lista_precio_id':fila['regla_canal'].lista_precio_id,
        'costo_version_id':fila['costo'].id,'huella_base':base,
        'cuenta_codigo':_texto(cuenta,'la cuenta declarada',100),
        'publicacion':_texto(publicacion,'la publicación declarada',160),
        'variante':str(variante or '').strip(),'modo_embalaje':modo,'detalle_ids':sorted(ids),
        'embalaje_incluido_centavos':sum(int(por_id[i].subtotal_centavos) for i in ids),
        'embalaje_adicional_centavos':adicional,
        'referencia':_texto(referencia,'la referencia que respalda el embalaje',300),
        'usuario_id':getattr(usuario,'id',None),'fecha':(ahora or ahora_utc_naive()).isoformat(),
        'identidad':'declarada_offline','publicacion_habilitada':False,
    }
    if len(evidencia['variante'])>160:raise ValueError('La variante supera 160 caracteres.')
    # Un reintento idéntico no agrega otra versión por su fecha/autor.
    anteriores=[e for e in historial if e.get('lista_precio_id')==evidencia['lista_precio_id']]
    comparables=set(evidencia)-{'version','fecha','usuario_id'}
    if anteriores and all(anteriores[-1].get(k)==evidencia[k] for k in comparables):return False
    evidencia['huella_evidencia']=_huella(evidencia)
    datos[CLAVE]=historial+[evidencia]
    inclusion.canales_json=json.dumps(datos,ensure_ascii=False,sort_keys=True)
    db_session.commit()
    return True


def ajustar_liquidacion(resultado, embalaje_centavos):
    """El embalaje externo al costo se descuenta una sola vez del neto."""
    return {**resultado,'embalaje_adicional_centavos':embalaje_centavos,
        'liquidacion_centavos':resultado['liquidacion_centavos']-embalaje_centavos}


def _utc(fecha):
    return fecha.astimezone(timezone.utc).replace(tzinfo=None) if fecha.tzinfo else fecha


def _contrastar(fila,evidencia,observaciones,reglas_validacion,ahora):
    lista_id=fila['regla_canal'].lista_precio_id;inclusion_id=fila['inclusion'].id
    reglas=[r for r in reglas_validacion if r.lista_precio_id==lista_id and r.vigente]
    motivos=[];encontradas={}
    if len(reglas)!=1:return {'estado':'pendiente','motivos':['Falta una regla de vigencia única para contrastar observaciones.'],'observaciones':{}}
    regla=reglas[0]
    if regla.estado!='vigente' or regla.vigente_desde is None or _utc(regla.vigente_desde)>ahora or (regla.vigente_hasta is not None and _utc(regla.vigente_hasta)<=ahora):
        return {'estado':'pendiente','motivos':['La regla de vigencia no está vigente en la fecha de cálculo.'],'observaciones':{}}
    if evidencia['variante']:motivos.append('Las observaciones actuales no identifican variantes; falta evidencia específica de esa variante.')
    for tipo,horas in [('precio',regla.vigencia_precio_horas),('cargo',regla.vigencia_cargos_horas),('envio',regla.vigencia_envio_horas)]:
        candidatas=[o for o in observaciones if o.organizacion_id==evidencia['organizacion_id'] and o.unidad_negocio_id==evidencia['unidad_negocio_id']
            and o.lista_precio_id==lista_id and o.catalogo_producto_id==inclusion_id and o.tipo==tipo
            and o.cuenta_codigo==evidencia['cuenta_codigo'] and o.referencia_publicacion==evidencia['publicacion']]
        if not candidatas:motivos.append(f'Falta observación de {tipo} para esa cuenta y publicación.');continue
        ultima=max(candidatas,key=lambda o:(_utc(o.fecha_observacion),o.id))
        iguales=[o for o in candidatas if _utc(o.fecha_observacion)==_utc(ultima.fecha_observacion)]
        if len(iguales)>1:
            campos={'precio':('precio_publicado_centavos',),'cargo':('comision_pct','cargo_fijo_centavos'),'envio':('costo_envio_centavos',)}[tipo]
            if any(any(getattr(o,c)!=getattr(ultima,c) for c in campos) for o in iguales):
                motivos.append(f'Observaciones contradictorias de {tipo} en la misma fecha.');continue
        if not 0<int(horas)<=87600 or _utc(ultima.fecha_observacion)>ahora or _utc(ultima.fecha_observacion)<ahora-timedelta(hours=int(horas)):
            motivos.append(f'Observación de {tipo} vencida o futura.');continue
        encontradas[tipo]=ultima
    from services.motor_comercial_canal import liquidar_precio
    precio=encontradas.get('precio');cargo=encontradas.get('cargo');envio=encontradas.get('envio');politica=fila['regla_canal']
    if precio is not None and precio.precio_publicado_centavos is not None:
        estimado=liquidar_precio(precio.precio_publicado_centavos,comision_pct=politica.comision_pct,
            publicidad_pct=politica.publicidad_pct,financiacion_pct=politica.financiacion_pct,devoluciones_pct=politica.devoluciones_pct,
            tramos=politica.tramos,umbral_envio_centavos=politica.umbral_envio_centavos,costo_envio_centavos=politica.costo_envio_default_centavos)
        if cargo and (cargo.comision_pct is None or cargo.cargo_fijo_centavos is None or Decimal(str(cargo.comision_pct))!=Decimal(str(politica.comision_pct)) or cargo.cargo_fijo_centavos!=estimado['cargo_fijo_centavos']):
            motivos.append('La comisión o cargo observado no coincide con la política al precio observado.')
        if envio and (envio.costo_envio_centavos is None or envio.costo_envio_centavos!=estimado['envio_centavos']):
            motivos.append('El envío observado no coincide con la política al precio observado.')
    elif precio is not None:motivos.append('La observación de precio no contiene importe.')
    return {'estado':'coincide_en_precio_observado' if not motivos else 'pendiente','motivos':motivos,
        'observaciones':{k:v.id for k,v in encontradas.items()},'precio_observado_centavos':getattr(precio,'precio_publicado_centavos',None)}


def completar_cobertura(fila, *, observaciones=(), reglas_validacion=(), ahora=None):
    """Completa la traza; declarar identidad no equivale a verificarla con APIs."""
    traza=deepcopy(fila['trazabilidad_economica']);base=traza.get('huella_base',traza['huella_enlace']);traza['huella_base']=base
    traza['cobertura_estado']='pendiente';traza['embalaje_adicional_centavos']=0
    traza['identidad_publicacion']=None;traza['contraste']={'estado':'pendiente','motivos':[],'observaciones':{}}
    try:
        _,historial=_json(fila['inclusion'])
        candidatas=[e for e in historial if e.get('lista_precio_id')==fila['regla_canal'].lista_precio_id]
        if not candidatas:
            traza['faltantes']=['Declarar el embalaje y la cuenta/publicación desde Gestionar.']
        else:
            e=candidatas[-1];sin_huella={k:v for k,v in e.items() if k!='huella_evidencia'}
            if _huella(sin_huella)!=e.get('huella_evidencia'):raise ValueError('La huella de la evidencia no coincide; requiere revisión.')
            traza['evidencia_embalaje']=e
            if (e['organizacion_id'],e['unidad_negocio_id'],e['catalogo_producto_id'],e['costo_version_id'],e['huella_base'])!=(traza['organizacion_id'],traza['unidad_negocio_id'],fila['inclusion'].id,fila['costo'].id,base):
                raise ValueError('Cambió el costo, catálogo o política: la evidencia anterior quedó obsoleta y debe revisarse.')
            extra=_importe(e['embalaje_adicional_centavos'])
            if e['modo_embalaje'] not in {'incluido','adicional','sin_costo'}:raise ValueError('La evidencia de embalaje no es válida.')
            if e['modo_embalaje']!='adicional' and extra:raise ValueError('La evidencia duplica el gasto de embalaje.')
            traza.update(cobertura_estado='declarada_vigente',embalaje_verificado=True,
                embalaje_adicional_centavos=extra,evidencia_embalaje=e,
                identidad_publicacion={k:e[k] for k in ('cuenta_codigo','publicacion','variante','identidad')})
            for tipo in ('minimo','objetivo'):
                piso=fila['pisos'][tipo]['piso_liquidacion_centavos']
                calculo=calcular_precio_minimo_canal(piso+extra,fila['regla_canal'])
                calculo=ajustar_liquidacion(calculo,extra);calculo['piso_liquidacion_centavos']=piso
                calculo['excedente_centavos']=calculo['liquidacion_centavos']-piso
                fila[tipo]=calculo;traza[tipo]=calculo
            traza['contraste']=_contrastar(fila,e,observaciones,reglas_validacion,_utc(ahora or ahora_utc_naive()))
            traza['faltantes']=traza['contraste']['motivos']+['La identidad es declarada offline; faltan cargos no cubiertos por las observaciones y validación con la cuenta.']
    except (ValueError,KeyError,TypeError) as error:
        traza.update(cobertura_estado='requiere_revision',embalaje_verificado=False)
        traza['faltantes']=[str(error)]
    # Coincidencias parciales no certifican todas las deducciones ni autorizan publicaciones.
    traza['cargos_contrastados_cuenta']=False;traza['habilita_publicacion']=False
    traza.pop('huella_enlace',None);traza['huella_enlace']=_huella(traza)
    fila['trazabilidad_economica']=traza
    return fila
