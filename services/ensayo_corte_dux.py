"""Ensayo integral en memoria entre snapshots exportados de DUX y Sistema Fierro."""
import hashlib,io,json

def _leer(archivo,nombre):
    contenido=archivo.read() if hasattr(archivo,"read") else archivo
    if not isinstance(contenido,bytes) or not contenido or len(contenido)>5_000_000:raise ValueError(f"{nombre} debe ser un JSON de hasta 5 MB.")
    try:documento=json.loads(contenido.decode("utf-8-sig"))
    except (UnicodeDecodeError,json.JSONDecodeError) as error:raise ValueError(f"{nombre} no es un JSON UTF-8 valido.") from error
    if not isinstance(documento,dict) or not isinstance(documento.get("productos"),list) or not isinstance(documento.get("pedidos_abiertos",[]),list):raise ValueError(f"{nombre} no contiene productos y pedidos_abiertos validos.")
    return documento

def _indexar_productos(filas,origen,hallazgos):
    indice={}
    for posicion,fila in enumerate(filas,1):
        if not isinstance(fila,dict):raise ValueError(f"Producto invalido en {origen}, fila {posicion}.")
        sku=str(fila.get("sku") or "").strip().upper()
        if not sku:raise ValueError(f"Falta SKU en {origen}, fila {posicion}.")
        if sku in indice:hallazgos.append({"codigo":"sku_duplicado","sku":sku,"origen":origen})
        indice[sku]={"stock":int(fila.get("stock",0)),"precio_centavos":int(fila.get("precio_centavos",0)),"activo":bool(fila.get("activo",True))}
    return indice

def _pedidos(filas,origen,hallazgos):
    ids=[]
    for fila in filas:
        identificador=str(fila.get("id_externo") if isinstance(fila,dict) else fila or "").strip()
        if not identificador:raise ValueError(f"Pedido abierto sin identificador en {origen}.")
        if identificador in ids:hallazgos.append({"codigo":"pedido_duplicado","pedido":identificador,"origen":origen})
        ids.append(identificador)
    return set(ids)

def ensayar_corte(snapshot_dux,snapshot_fierro,*,organizacion_id):
    dux=_leer(snapshot_dux,"Snapshot DUX");fierro=_leer(snapshot_fierro,"Snapshot Fierro")
    if fierro.get("organizacion_id")!=int(organizacion_id):raise ValueError("El snapshot Fierro pertenece a otro tenant.")
    hallazgos=[];a=_indexar_productos(dux["productos"],"dux",hallazgos);b=_indexar_productos(fierro["productos"],"fierro",hallazgos)
    diferencias=[]
    for sku in sorted(set(a)|set(b)):
        if sku not in a:diferencias.append({"sku":sku,"tipo":"solo_fierro"});continue
        if sku not in b:diferencias.append({"sku":sku,"tipo":"faltante_fierro"});continue
        for campo in ("stock","precio_centavos","activo"):
            if a[sku][campo]!=b[sku][campo]:diferencias.append({"sku":sku,"tipo":campo,"dux":a[sku][campo],"fierro":b[sku][campo]})
    pa=_pedidos(dux.get("pedidos_abiertos",[]),"dux",hallazgos);pb=_pedidos(fierro.get("pedidos_abiertos",[]),"fierro",hallazgos)
    pedidos={"faltantes_fierro":sorted(pa-pb),"solo_fierro":sorted(pb-pa),"coincidentes":len(pa&pb)}
    if diferencias:hallazgos.append({"codigo":"diferencias_productos","cantidad":len(diferencias)})
    if pedidos["faltantes_fierro"] or pedidos["solo_fierro"]:hallazgos.append({"codigo":"diferencias_pedidos","cantidad":len(pedidos["faltantes_fierro"])+len(pedidos["solo_fierro"])})
    resultado={"organizacion_id":int(organizacion_id),"modo":"ensayo_corte_dux_offline","aprobado":not hallazgos,"autorizacion_corte":False,"resumen":{"productos_dux":len(a),"productos_fierro":len(b),"diferencias_productos":len(diferencias),"pedidos_dux":len(pa),"pedidos_fierro":len(pb),"hallazgos":len(hallazgos)},"diferencias_productos":diferencias,"pedidos_abiertos":pedidos,"hallazgos":hallazgos,"controles":{"consultas_dux":0,"consultas_canales":0,"datos_persistidos":0,"stock_modificado":0,"precios_publicados":0,"pedidos_creados":0,"facturas_emitidas":0,"conexiones_externas":0}}
    resultado["huella_ensayo"]=hashlib.sha256(json.dumps(resultado,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest();return resultado

def exportar_ensayo(resultado):return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode())
