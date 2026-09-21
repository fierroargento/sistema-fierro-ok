"""Snapshots locales de solo lectura para el ensayo de reemplazo de DUX."""
import hashlib,io,json
TERMINALES={"Finalizado","Entregado","No Entregado"}

def construir_snapshot_fierro(*,organizacion_id,unidad_negocio_id,productos,inclusiones,existencias,pedidos):
    precios={}
    for item in inclusiones:
        if getattr(item,"activo",False):precios[int(item.producto_id)]=int(item.precio_lista_centavos if item.precio_lista_centavos is not None else item.precio_centavos)
    stocks={}
    for existencia in existencias:stocks[int(existencia.producto_id)]=stocks.get(int(existencia.producto_id),0)+int(existencia.stock_actual)
    filas=[{"sku":str(p.sku).strip().upper(),"stock":stocks.get(int(p.id),0),"precio_centavos":precios.get(int(p.id),0),"activo":int(p.id) in precios} for p in sorted(productos,key=lambda x:(str(x.sku).upper(),x.id))]
    abiertos=[]
    for p in pedidos:
        if getattr(p,"estado",None) in TERMINALES:continue
        referencia=getattr(p,"id_venta",None) or getattr(p,"ml_pack_id",None) or getattr(p,"tn_order_id",None) or f"FIERRO-{p.id}"
        abiertos.append({"id_externo":str(referencia)})
    resultado={"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),"origen":"sistema_fierro","modo":"snapshot_solo_lectura","productos":filas,"pedidos_abiertos":sorted(abiertos,key=lambda x:x["id_externo"]),"controles":{"datos_persistidos":0,"stock_modificado":0,"precios_modificados":0,"pedidos_modificados":0,"conexiones_externas":0}}
    resultado["huella_snapshot"]=hashlib.sha256(json.dumps(resultado,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest();return resultado

def plantilla_snapshot_dux():return {"origen":"dux_exportado_manualmente","productos":[{"sku":"EJEMPLO-SKU","stock":0,"precio_centavos":0,"activo":True}],"pedidos_abiertos":[{"id_externo":"EJEMPLO-PEDIDO"}]}
def exportar(documento):return io.BytesIO(json.dumps(documento,ensure_ascii=False,sort_keys=True,indent=2).encode())
