"""Traslado acotado de materiales y fabricación reales, sin duplicar identidades.

Por defecto simula en READ ONLY. --aplicar exige separación de bases verificada
por el operador. No importa app.py, ni inicia scheduler ni conexiones de canales.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from types import SimpleNamespace
from sqlalchemy import MetaData,Table,create_engine,select,update,text
from scripts.traslado_fierro_alcance import SKU_REALES,INSUMOS_REALES


def ejecutar(engine,origen,destino,*,aplicar=False,mapa=None,proveedor=None,bases_separadas=False,skus=SKU_REALES,codigos=INSUMOS_REALES):
    if aplicar and not bases_separadas:raise ValueError('Primero verificá en Render que staging y producción tengan bases separadas.')
    mapa=mapa or {};resultado={'modo':'aplicar' if aplicar else 'simulacion','aplicado':False,'bloqueos':[],'dependencias':[],'disponibles':{},'cantidades':{},'equivalencia_codimat':{'1985':'3951'}}
    with engine.connect() as c:
        with c.begin():
            if c.dialect.name=='postgresql':
                if not aplicar:c.execute(text('SET TRANSACTION READ ONLY'))
                if c.execute(text('SELECT current_database()')).scalar_one()!='sistema_fierro_staging':raise ValueError('La base no es sistema_fierro_staging.')
                if aplicar:c.execute(text("SET LOCAL lock_timeout = '5s'"))
            elif c.dialect.name!='sqlite':raise ValueError('Motor no admitido.')
            meta=MetaData();tablas={}
            def tabla(n):
                if n not in tablas:tablas[n]=Table(n,meta,autoload_with=c,resolve_fks=False)
                return tablas[n]
            def filas(t,condicion):return [dict(r) for r in c.execute(select(t).where(condicion)).mappings()]
            u=tabla('unidad_negocio');q=select(u).where(u.c.id.in_([origen,destino])).order_by(u.c.id)
            if aplicar:q=q.with_for_update()
            unidades={r['id']:dict(r) for r in c.execute(q).mappings()}
            if origen==destino or set(unidades)!={origen,destino}:raise ValueError('Origen y destino inválidos.')
            a,b=unidades[origen],unidades[destino];org=a['organizacion_id']
            if org!=b['organizacion_id'] or a['codigo']!='ensayo-uat' or b['codigo']!='fierro-100-argento' or not b['activa']:raise ValueError('Las unidades no son Ensayo UAT y Fierro de la misma empresa activa.')
            # Se bloquea el conjunto completo durante el traslado. La simulación no bloquea ni escribe.
            def bloquear(t,condicion=None):
                if aplicar:
                    q=select(t.c.id)
                    if condicion is not None:q=q.where(condicion)
                    elif 'organizacion_id' in t.c:q=q.where(t.c.organizacion_id==org)
                    c.execute(q.order_by(t.c.id).with_for_update()).all()
            i=tabla('insumo_productivo');p=tabla('producto');f=tabla('perfil_costeo_producto');v=tabla('costo_producto_version')
            for t in (i,p,f,v):bloquear(t)
            materiales=filas(i,(i.c.organizacion_id==org)&i.c.codigo.in_(codigos))
            productos=filas(p,(p.c.organizacion_id==org)&p.c.sku.in_(skus))
            if len(materiales)!=len(codigos) or len(productos)!=len(skus):resultado['bloqueos'].append('Faltan identidades del inventario revisado. No se crean ni se deducen por nombre.')
            ids={r['id'] for r in materiales};pids={r['id'] for r in productos}
            if any(r['unidad_negocio_id'] not in (origen,destino) for r in materiales):resultado['bloqueos'].append('Hay materiales en otra unidad; revisar sin apropiarlos.')
            perfiles=filas(f,(f.c.organizacion_id==org)&f.c.producto_id.in_(pids)&(f.c.unidad_negocio_id==origen))
            fids={r['id'] for r in perfiles}
            existentes=filas(f,(f.c.organizacion_id==org)&f.c.producto_id.in_({r['producto_id'] for r in perfiles})&(f.c.unidad_negocio_id==destino))
            if existentes:resultado['bloqueos'].append('Fierro ya tiene perfiles para algunos productos. Requiere conciliación sin duplicar.')
            versiones=filas(v,(v.c.organizacion_id==org)&v.c.producto_id.in_(pids)&(v.c.unidad_negocio_id==origen))
            for r in versiones:
                if r['vigente'] or r['estado']!='preparatorio':resultado['bloqueos'].append('Hay costos reales vigentes/no preparatorios: requieren revisión específica.')
            if versiones and filas(v,(v.c.organizacion_id==org)&v.c.producto_id.in_({r['producto_id'] for r in versiones})&(v.c.unidad_negocio_id==destino)):
                resultado['bloqueos'].append('Fierro ya tiene versiones de costo de estos productos; no se renumeran automáticamente.')
            ajustes=[];tarifas_reasignadas={}
            ficha=tabla('producto_ficha_maestra')
            if aplicar:c.execute(select(ficha.c.producto_id).where(ficha.c.organizacion_id==org,ficha.c.producto_id.in_(pids)).order_by(ficha.c.producto_id).with_for_update()).all()
            fichas={r['producto_id']:r for r in filas(ficha,(ficha.c.organizacion_id==org)&ficha.c.producto_id.in_(pids))}
            lineas_por_perfil={r['id']:str(fichas.get(r['producto_id'],{}).get('linea') or '').strip() for r in perfiles}
            for nombre,campo,recurso in [('producto_insumo_costeo','insumo_id','insumo_productivo'),('producto_operacion_costeo','empleado_id','empleado_productivo'),('producto_maquina_costeo','maquina_id','maquina_productiva'),('producto_costo_fijo_costeo','costo_fijo_id','costo_fijo_productivo')]:
                t=tabla(nombre);bloquear(t,t.c.perfil_costeo_id.in_(fids));lineas=filas(t,t.c.perfil_costeo_id.in_(fids));rt=tabla(recurso);bloquear(rt)
                usados=Counter(r[campo] for r in lineas)
                for rid,cantidad in sorted(usados.items()):
                    rr=filas(rt,rt.c.id==rid)
                    if not rr or rr[0]['organizacion_id']!=org:
                        resultado['bloqueos'].append(f'{recurso} {rid}: referencia ajena o inexistente.');continue
                    r=rr[0]
                    valido=r['unidad_negocio_id']==destino or (recurso=='insumo_productivo' and rid in ids and r['unidad_negocio_id']==origen)
                    if valido:continue
                    opciones=filas(rt,(rt.c.organizacion_id==org)&(rt.c.unidad_negocio_id==destino))
                    resultado['disponibles'][recurso]=[{k:x[k] for k in ('id','codigo','nombre','activo') if k in x} for x in opciones]
                    grupos={}
                    for linea in lineas:
                        if linea[campo]==rid:grupos.setdefault(lineas_por_perfil[linea['perfil_costeo_id']],[]).append(linea)
                    for grupo,afectadas in sorted(grupos.items()):
                        if not grupo:
                            resultado['bloqueos'].append(f'Hay perfiles sin línea en su ficha maestra para {recurso} {rid}. Revisá la clasificación antes de reasignar.')
                        nuevo=mapa.get('por_linea',{}).get(grupo,{}).get(recurso,{}).get(str(rid),mapa.get(recurso,{}).get(str(rid)))
                        resultado['dependencias'].append({'tabla':recurso,'id':rid,'codigo':r.get('codigo'),'nombre':r.get('nombre'),'linea_producto':grupo,'lineas':len(afectadas),'reemplazo':nuevo})
                        candidatos=[x for x in opciones if str(x['id'])==str(nuevo) and x.get('activo',True)]
                        if recurso=='insumo_productivo' or not candidatos:
                            resultado['bloqueos'].append(f'{recurso} {rid} / {grupo}: falta seleccionar un recurso real activo de Fierro.');continue
                        for linea in afectadas:
                            if recurso=='empleado_productivo':tarifas_reasignadas[(linea['perfil_costeo_id'],str(rid))]=candidatos[0]['id']
                            ajustes.append((nombre,linea['id'],campo,candidatos[0]['id']))
            combo=tabla('combo_producto_componente');bloquear(combo,combo.c.combo_perfil_id.in_(fids)|combo.c.componente_perfil_id.in_(fids))
            aristas=filas(combo,combo.c.combo_perfil_id.in_(fids)|combo.c.componente_perfil_id.in_(fids))
            todos_perfiles={r['id']:r for r in filas(f,f.c.id.in_({x[k] for x in aristas for k in ('combo_perfil_id','componente_perfil_id')}))}
            for arista in aristas:
                for k in ('combo_perfil_id','componente_perfil_id'):
                    r=todos_perfiles.get(arista[k])
                    if not r or r['organizacion_id']!=org or (r['id'] not in fids and r['unidad_negocio_id']!=destino):resultado['bloqueos'].append('Un combo cruza perfiles que no forman parte del traslado.')
            # Vincular códigos confirmados al proveedor existente, sin renombrar el insumo 1985.
            l=tabla('material_proveedor_compra');bloquear(l);vinculos=[];codigos_a_actualizar=[]
            if proveedor is not None:
                pr=tabla('proveedor_compra');pu=tabla('proveedor_unidad')
                pp=filas(pr,(pr.c.id==proveedor)&(pr.c.organizacion_id==org))
                miembros=filas(pu,(pu.c.proveedor_id==proveedor)&(pu.c.organizacion_id==org)&(pu.c.unidad_negocio_id==destino)&(pu.c.estado=='activo'))
                if not pp or not miembros or 'CODIMAT' not in pp[0]['razon_social'].upper():resultado['bloqueos'].append('Elegí el proveedor Codimat activo de Fierro.')
                else:
                    from services.listas_codimat import DESCUENTOS
                    por_codigo={r['codigo']:r for r in materiales}
                    for codigo in DESCUENTOS:
                        material=por_codigo.get('1985' if codigo=='3951' else codigo)
                        if not material:resultado['bloqueos'].append('Falta material para Codimat '+codigo);continue
                        existentes=filas(l,(l.c.organizacion_id==org)&(l.c.unidad_negocio_id==destino)&(l.c.proveedor_id==proveedor)&((l.c.codigo_clave==codigo)|(l.c.insumo_id==material['id'])))
                        if codigo=='3951' and len(existentes)==1 and existentes[0]['codigo_clave']=='1985' and existentes[0]['insumo_id']==material['id']:codigos_a_actualizar.append(existentes[0]['id'])
                        elif existentes and not all(r['codigo_clave']==codigo and r['insumo_id']==material['id'] for r in existentes):resultado['bloqueos'].append('Vínculo incompatible para Codimat '+codigo)
                        elif not existentes:vinculos.append(dict(organizacion_id=org,unidad_negocio_id=destino,proveedor_id=proveedor,insumo_id=material['id'],codigo=codigo,codigo_clave=codigo))
            else:
                pr=tabla('proveedor_compra');pu=tabla('proveedor_unidad')
                disponibles=c.execute(select(pr.c.id,pr.c.codigo,pr.c.razon_social).join(pu,pu.c.proveedor_id==pr.c.id).where(pr.c.organizacion_id==org,pu.c.organizacion_id==org,pu.c.unidad_negocio_id==destino,pu.c.estado=='activo')).mappings()
                resultado['disponibles']['proveedores_codimat']=[dict(r) for r in disponibles if 'CODIMAT' in r['razon_social'].upper()]
                resultado['bloqueos'].append('Indicá --proveedor-codimat con el ID del proveedor activo de Fierro para preparar los 13 vínculos.')
            resultado['cantidades']={'materiales_a_trasladar':sum(r['unidad_negocio_id']==origen for r in materiales),'perfiles':len(perfiles),'versiones_preparatorias':len(versiones),'lineas_a_reasignar':len(ajustes),'vinculos_codimat':len(vinculos),'codigos_a_actualizar':len(codigos_a_actualizar)}
            # Huella útil para comparar simulaciones; no incluye precios ni datos personales.
            resultado['huella']=sha256(json.dumps([sorted(ids),sorted(fids),sorted(r['id'] for r in versiones),ajustes,vinculos,codigos_a_actualizar],sort_keys=True).encode()).hexdigest()
            resultado['bloqueos']=sorted(set(resultado['bloqueos']))
            if not aplicar or resultado['bloqueos']:return resultado
            for nombre,ident,campo,nuevo in ajustes:c.execute(update(tabla(nombre)).where(tabla(nombre).c.id==ident).values({campo:nuevo}))
            # Mantener despiece y composición bajo la misma huella después de reasignar mano de obra.
            despiece=tabla('producto_despiece_costeo')
            from services.productos_despiece import huella_perfil
            for r in filas(despiece,despiece.c.perfil_costeo_id.in_(fids)):
                contenido=json.loads(r['contenido']);tarifa=str(contenido.get('tarifa_id') or '')
                nueva_tarifa=tarifas_reasignadas.get((r['perfil_costeo_id'],tarifa))
                if nueva_tarifa is not None:
                    contenido['tarifa_id']=int(nueva_tarifa)
                    insumos=[SimpleNamespace(**x) for x in filas(tabla('producto_insumo_costeo'),tabla('producto_insumo_costeo').c.perfil_costeo_id==r['perfil_costeo_id'])]
                    operaciones=[SimpleNamespace(**x) for x in filas(tabla('producto_operacion_costeo'),tabla('producto_operacion_costeo').c.perfil_costeo_id==r['perfil_costeo_id'])]
                    huella=huella_perfil(SimpleNamespace(insumos_costeo=insumos,operaciones_costeo=operaciones))
                    c.execute(update(despiece).where(despiece.c.perfil_costeo_id==r['perfil_costeo_id']).values(contenido=json.dumps(contenido,ensure_ascii=False,sort_keys=True),huella_composicion=huella,revision=r['revision']+1))
            for t,seleccion in [(i,ids),(f,fids),(v,{r['id'] for r in versiones})]:
                c.execute(update(t).where(t.c.id.in_(seleccion),t.c.organizacion_id==org,t.c.unidad_negocio_id==origen).values(unidad_negocio_id=destino))
            if codigos_a_actualizar:c.execute(update(l).where(l.c.id.in_(codigos_a_actualizar)).values(codigo='3951',codigo_clave='3951'))
            if vinculos:c.execute(l.insert(),vinculos)
            # Quedan pruebas e historial de importaciones en UAT; no se eliminan en este traslado.
            resultado['aplicado']=True
            resultado['nota']='Recetas y precios históricos conservados. Costos preparatorios no recalculados ni activados. Ensayo UAT sigue pendiente de retiro final.'
    return resultado


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staging',action='store_true',required=True)
    parser.add_argument('--origen',type=int,required=True);parser.add_argument('--destino',type=int,required=True)
    parser.add_argument('--proveedor-codimat',type=int);parser.add_argument('--mapa')
    parser.add_argument('--aplicar',action='store_true');parser.add_argument('--bases-separadas-verificadas',action='store_true')
    args=parser.parse_args()
    if os.getenv('MODO_LABORATORIO_DESCONECTADO','').lower() not in ('true','1','si') or os.getenv('RENDER_GIT_BRANCH')!='integracion-saas-2026-09' or 'staging' not in os.getenv('RENDER_EXTERNAL_URL','').lower():raise SystemExit('Se requiere staging de integración con laboratorio desconectado.')
    url=os.getenv('DATABASE_URL','')
    if not url:raise SystemExit('Falta la base del servicio.')
    if url.startswith('postgres://'):url='postgresql://'+url[len('postgres://'):]
    mapa=json.load(open(args.mapa)) if args.mapa else {}
    engine=create_engine(url)
    try:
        resultado=ejecutar(engine,args.origen,args.destino,aplicar=args.aplicar,mapa=mapa,proveedor=args.proveedor_codimat,bases_separadas=args.bases_separadas_verificadas)
        print(json.dumps(resultado,ensure_ascii=False,indent=2,default=str))
        if args.aplicar and not resultado['aplicado']:raise SystemExit(2)
    finally:engine.dispose()

if __name__=='__main__':main()
