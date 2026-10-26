"""Asignaciones preparatorias multi-CUIT, independientes de unidades comerciales."""
import hashlib
import json
from models.sucursal_fiscal import SucursalFiscal, ContextoFiscalBorrador
from scripts.preparar_sucursales_fiscales import preparado


def huella(sucursal, session):
    filas = session.query(SucursalFiscal).filter_by(organizacion_id=sucursal.organizacion_id, sucursal_id=sucursal.id).order_by(SucursalFiscal.id).all()
    return hashlib.sha256(json.dumps([(f.entidad_fiscal_id, f.punto_venta_fiscal_id, f.predeterminado) for f in filas]).encode()).hexdigest()


def guardar(form, *, organizacion_id, modelos, session):
    if not preparado(session.connection()):
        raise ValueError('Falta preparar las asignaciones fiscales en la base de datos.')
    sucursal = modelos['SucursalOperativa'].query.filter_by(id=form.get('sucursal_id'), organizacion_id=organizacion_id).with_for_update().first()
    if sucursal is None:
        raise ValueError('La sucursal no pertenece a la empresa.')
    if form.get('huella') != huella(sucursal, session):
        raise ValueError('La asignación cambió. Recargá la página antes de guardar.')
    puntos_ids = form.getlist('punto_id')
    puntos = []
    for valor in puntos_ids:
        punto = modelos['PuntoVentaFiscal'].query.filter_by(id=valor, organizacion_id=organizacion_id).first()
        if punto is None or punto.entidad_fiscal.organizacion_id != organizacion_id or punto.configuracion.organizacion_id != organizacion_id or punto.configuracion.entidad_fiscal_id != punto.entidad_fiscal_id:
            raise ValueError('El punto de venta o su CUIT no pertenece a la empresa.')
        puntos.append(punto)
    if len({p.entidad_fiscal_id for p in puntos}) != len(puntos):
        raise ValueError('Elegí un solo punto de venta por CUIT para esta sucursal.')
    predeterminado = str(form.get('predeterminado') or '')
    if puntos and predeterminado not in {str(p.id) for p in puntos}:
        raise ValueError('Elegí como predeterminado uno de los puntos seleccionados.')
    session.query(SucursalFiscal).filter_by(organizacion_id=organizacion_id, sucursal_id=sucursal.id).delete(synchronize_session=False)
    for punto in puntos:
        session.add(SucursalFiscal(organizacion_id=organizacion_id, sucursal_id=sucursal.id,
            entidad_fiscal_id=punto.entidad_fiscal_id, punto_venta_fiscal_id=punto.id,
            predeterminado=str(punto.id) == predeterminado))
    session.flush()
    return sucursal


def validar_seleccion(form, *, organizacion_id, entidad, punto, modelos, session):
    valor = form.get('sucursal_id')
    if not preparado(session.connection()):
        if valor:
            raise ValueError('Falta preparar las asignaciones fiscales.')
        return None
    # Las altas manuales nuevas exigen sucursal; los borradores históricos no se alteran.
    sucursal = modelos['SucursalOperativa'].query.filter_by(id=valor, organizacion_id=organizacion_id).first() if valor else None
    if sucursal is None:
        raise ValueError('Elegí la sucursal del comprobante.')
    vinculo = session.query(SucursalFiscal).filter_by(organizacion_id=organizacion_id, sucursal_id=sucursal.id,
        entidad_fiscal_id=entidad.id, punto_venta_fiscal_id=punto.id).first()
    if vinculo is None:
        raise ValueError('El CUIT y punto de venta no están asignados a esa sucursal.')
    return sucursal


def guardar_contexto(borrador, sucursal, entidad, punto, session):
    if sucursal is not None:
        session.add(ContextoFiscalBorrador(borrador_id=borrador.id, organizacion_id=borrador.organizacion_id,
            sucursal_id=sucursal.id, sucursal_nombre=sucursal.nombre, razon_social=entidad.razon_social,
            cuit=entidad.cuit, condicion_iva=entidad.condicion_iva, domicilio_fiscal=entidad.domicilio_fiscal,
            punto_venta_numero=punto.numero))
