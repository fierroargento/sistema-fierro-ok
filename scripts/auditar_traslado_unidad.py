"""Inventario de sólo lectura previo a retirar una unidad de ensayo en staging.

No importa app.py, no inicia tareas y no realiza traslados. No imprime credenciales.
"""
import argparse
import json
import os
from sqlalchemy import MetaData,Table,create_engine,inspect,select,func,text


def auditar(engine, *, detalle=False, origen=None, destino=None):
    resultado={'solo_lectura':True,'unidades':[],'referencias':[],'advertencias':[]}
    with engine.connect() as conexion:
        with conexion.begin():
            if engine.dialect.name=='postgresql':
                conexion.execute(text('SET TRANSACTION READ ONLY'))
                resultado['base']=conexion.execute(text('SELECT current_database()')).scalar_one()
            elif engine.dialect.name=='sqlite':
                conexion.execute(text('PRAGMA query_only=ON'))
                resultado['base']='SQLite local de prueba'
            else:raise ValueError('Motor no admitido para esta auditoría.')
            inspector=inspect(conexion)
            nombres=inspector.get_table_names()
            if 'unidad_negocio' not in nombres:raise ValueError('No se encontró el maestro de unidades.')
            metadata=MetaData()
            unidades=Table('unidad_negocio',metadata,autoload_with=conexion,resolve_fks=False)
            campos=[unidades.c[n] for n in ['id','organizacion_id','codigo','nombre','activa'] if n in unidades.c]
            resultado['unidades']=[dict(r) for r in conexion.execute(select(*campos).order_by(unidades.c.id)).mappings()]
            if detalle:
                por_id={u['id']:u for u in resultado['unidades']}
                if origen not in por_id or destino not in por_id or origen==destino:raise ValueError('Elegí unidades de origen y destino existentes y distintas.')
                if por_id[origen].get('organizacion_id')!=por_id[destino].get('organizacion_id'):raise ValueError('Origen y destino deben pertenecer a la misma organización.')
                resultado['alcance']={'origen':origen,'destino':destino}
            for nombre in sorted(nombres):
                columnas={c['name'] for c in inspector.get_columns(nombre)}
                fks=inspector.get_foreign_keys(nombre)
                referencias={col for fk in fks if fk.get('referred_table')=='unidad_negocio' for col in fk['constrained_columns']}
                if 'unidad_negocio_id' in columnas:referencias.add('unidad_negocio_id')
                if not referencias:continue
                tabla=Table(nombre,metadata,autoload_with=conexion,resolve_fks=False)
                for columna in sorted(referencias):
                    conteo=select(tabla.c[columna],func.count()).where(tabla.c[columna].is_not(None)).group_by(tabla.c[columna]).order_by(tabla.c[columna])
                    grupos=[{'unidad_id':r[0],'cantidad':r[1]} for r in conexion.execute(conteo)]
                    if not grupos:continue
                    referencia={'tabla':nombre,'columna':columna,'por_unidad':grupos,'claves_unicas':inspector.get_unique_constraints(nombre)}
                    if detalle:
                        if not any(g['unidad_id']==origen for g in grupos):continue
                        # Lista explícita: no se vuelcan contraseñas, teléfonos, sueldos ni tokens.
                        permitidos=('id','organizacion_id','codigo','sku','nombre','numero','tipo','estado','activo','vigente','producto_id','insumo_id','perfil_id','empleado_id','proveedor_id','recurso_id','maquina_id','tarifa_id','numero_version','unidad_negocio_id')
                        seleccion=[tabla.c[n] for n in permitidos if n in tabla.c]
                        if not seleccion:seleccion=[tabla.c[columna]]
                        consulta=select(*seleccion).where(tabla.c[columna]==origen)
                        if 'id' in tabla.c:consulta=consulta.order_by(tabla.c.id)
                        filas=[dict(r) for r in conexion.execute(consulta.limit(1001)).mappings()]
                        referencia['detalle_truncado']=len(filas)>1000
                        referencia['registros_origen']=filas[:1000]
                        referencia['referencias_externas']=fks
                        referencia['indices_unicos']=[i for i in inspector.get_indexes(nombre) if i.get('unique')]
                        if 'producto_id' in tabla.c and 'producto' in nombres:
                            productos=Table('producto',metadata,autoload_with=conexion,resolve_fks=False,extend_existing=True)
                            ids={r.get('producto_id') for r in filas[:1000]}-{None}
                            cols=[productos.c[n] for n in ('id','organizacion_id','sku','nombre') if n in productos.c]
                            referencia['productos']=[dict(r) for r in conexion.execute(select(*cols).where(productos.c.id.in_(ids))).mappings()] if ids else []
                    resultado['referencias'].append(referencia)
            resultado['advertencias']=[
                'El inventario no clasifica datos reales frente a pruebas y no autoriza mover todo indiscriminadamente.',
                'Comparar el recurso de base asociado a staging y producción en Render. El nombre mostrado no prueba por sí solo que sean bases distintas.',
                'Revisar referencias indirectas, composiciones, históricos y restricciones antes de trasladar. No borrar ni desactivar la unidad hasta completar esa revisión.',
                'No se modificaron unidades, registros, precios ni movimientos.'
            ]
    return resultado


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staging',action='store_true',required=True)
    parser.add_argument('--detalle',action='store_true')
    parser.add_argument('--origen',type=int)
    parser.add_argument('--destino',type=int)
    args=parser.parse_args()
    if args.detalle and (args.origen is None or args.destino is None):parser.error('--detalle requiere --origen y --destino')
    if os.getenv('MODO_LABORATORIO_DESCONECTADO','').lower() not in {'true','1','si'}:raise SystemExit('Se requiere laboratorio desconectado.')
    if os.getenv('RENDER_GIT_BRANCH')!='integracion-saas-2026-09':raise SystemExit('Se requiere la rama de integración.')
    if 'staging' not in os.getenv('RENDER_EXTERNAL_URL','').lower():raise SystemExit('Se requiere el servicio de staging.')
    url=os.getenv('DATABASE_URL','')
    if not url:raise SystemExit('No se encontró la base del servicio.')
    if url.startswith('postgres://'):url='postgresql://'+url[len('postgres://'):]
    engine=create_engine(url)
    try:print(json.dumps(auditar(engine,detalle=args.detalle,origen=args.origen,destino=args.destino),ensure_ascii=False,indent=2,default=str))
    finally:engine.dispose()

if __name__=='__main__':main()
