"""Convierte exportaciones CSV de DUX a un snapshot JSON sin conexiones externas."""
import csv,hashlib,io,json
def _filas(archivo,nombre):
 contenido=archivo.read() if hasattr(archivo,"read") else archivo
 if not isinstance(contenido,bytes) or not contenido or len(contenido)>5_000_000:raise ValueError(f"{nombre} debe ser un CSV de hasta 5 MB.")
 try:texto=contenido.decode("utf-8-sig")
 except UnicodeDecodeError as error:raise ValueError(f"{nombre} no esta codificado en UTF-8.") from error
 try:separador=csv.Sniffer().sniff(texto[:4096],delimiters=",;\t").delimiter
 except csv.Error:separador=";"
 return [{str(k or "").strip().upper():str(v or "").strip() for k,v in fila.items()} for fila in csv.DictReader(io.StringIO(texto),delimiter=separador)]
def _entero(valor,campo,fila):
 limpio=str(valor or "0").strip().replace("$","").replace(" ","")
 if "," in limpio and "." in limpio:limpio=limpio.replace(".","").replace(",",".")
 elif "," in limpio:limpio=limpio.replace(",",".")
 try:return int(round(float(limpio)))
 except ValueError as error:raise ValueError(f"{campo} invalido en fila {fila}.") from error
def convertir_exportaciones(productos_csv,pedidos_csv=None):
 productos=[];vistos=set()
 for numero,fila in enumerate(_filas(productos_csv,"Productos DUX"),2):
  sku=(fila.get("SKU") or fila.get("CODIGO") or "").strip().upper()
  if not sku:raise ValueError(f"Falta SKU o CODIGO en fila {numero}.")
  if sku in vistos:raise ValueError(f"SKU duplicado en exportacion DUX: {sku}.")
  vistos.add(sku);activo=(fila.get("ACTIVO") or "SI").strip().lower() in {"si","sí","s","1","true","activo"};productos.append({"sku":sku,"stock":_entero(fila.get("STOCK"),"STOCK",numero),"precio_centavos":_entero(fila.get("PRECIO_CENTAVOS") or fila.get("PRECIO"),"PRECIO",numero),"activo":activo})
 pedidos=[];ids=set()
 if pedidos_csv:
  for numero,fila in enumerate(_filas(pedidos_csv,"Pedidos DUX"),2):
   identificador=(fila.get("ID_EXTERNO") or fila.get("ID_VENTA") or fila.get("PEDIDO") or "").strip()
   if not identificador:raise ValueError(f"Falta ID_EXTERNO, ID_VENTA o PEDIDO en fila {numero}.")
   if identificador in ids:raise ValueError(f"Pedido duplicado en exportacion DUX: {identificador}.")
   ids.add(identificador);pedidos.append({"id_externo":identificador})
 resultado={"origen":"dux_exportado_manualmente","modo":"conversion_csv_offline","productos":sorted(productos,key=lambda x:x["sku"]),"pedidos_abiertos":sorted(pedidos,key=lambda x:x["id_externo"]),"controles":{"consultas_dux":0,"datos_persistidos":0,"stock_modificado":0,"precios_modificados":0,"pedidos_modificados":0,"conexiones_externas":0}}
 resultado["huella_snapshot"]=hashlib.sha256(json.dumps(resultado,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest();return resultado
def exportar(resultado):return io.BytesIO(json.dumps(resultado,ensure_ascii=False,sort_keys=True,indent=2).encode())
def plantilla_productos():return io.BytesIO(b"SKU;STOCK;PRECIO_CENTAVOS;ACTIVO\nEJEMPLO-SKU;0;0;SI\n")
def plantilla_pedidos():return io.BytesIO(b"ID_EXTERNO\nEJEMPLO-PEDIDO\n")
