"""Aceptación integral de un ciclo operativo simulado, completamente en memoria."""
import hashlib,io,json

DOMINIOS=("catalogo","pedido","compras","produccion","inventario","facturacion","tesoreria","contabilidad","postventa")
def _entero(v,campo,minimo=0):
 try:n=int(v)
 except (TypeError,ValueError):raise ValueError(f"{campo} debe ser un entero.")
 if n<minimo:raise ValueError(f"{campo} debe ser mayor o igual a {minimo}.")
 return n
def _leer(archivo):
 contenido=archivo.read() if hasattr(archivo,"read") else archivo
 if not isinstance(contenido,bytes) or not contenido or len(contenido)>2_000_000:raise ValueError("El escenario debe ser un JSON de hasta 2 MB.")
 try:d=json.loads(contenido.decode("utf-8-sig"))
 except (UnicodeDecodeError,json.JSONDecodeError) as e:raise ValueError("El escenario no es JSON UTF-8 valido.") from e
 if not isinstance(d,dict):raise ValueError("El escenario debe ser un objeto JSON.")
 return d
def plantilla(*,organizacion_id,unidad_negocio_id):
 d={"version":1,"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),"catalogo":{"producto_id":101,"sku":"PRUEBA-001","costo_unitario_centavos":6000,"precio_unitario_centavos":10000},"pedido":{"pedido_id":201,"producto_id":101,"cantidad":5,"total_centavos":50000},"compras":{"importe_insumos_centavos":30000},"produccion":{"producto_id":101,"cantidad_planificada":5,"cantidad_buena":5,"cantidad_rechazada":0,"costo_resultado_centavos":30000},"inventario":{"stock_inicial":2,"producido":5,"despachado":5,"reservado_final":0,"stock_final":2},"facturacion":{"pedido_id":201,"total_borrador_centavos":50000,"emitida":False},"tesoreria":{"ingreso_proyectado_centavos":50000,"cobrado":False},"contabilidad":{"debe_centavos":50000,"haber_centavos":50000,"contabilizado":False},"postventa":{"pedido_id":201,"cantidad_afectada":0,"exposicion_centavos":0,"ejecutada":False}}
 return io.BytesIO(json.dumps(d,ensure_ascii=False,indent=2).encode("utf-8"))
def evaluar(archivo,*,organizacion_id,unidad_negocio_id):
 d=_leer(archivo)
 if int(d.get("organizacion_id",-1))!=int(organizacion_id):raise ValueError("El escenario pertenece a otro tenant.")
 if int(d.get("unidad_negocio_id",-1))!=int(unidad_negocio_id):raise ValueError("El escenario pertenece a otra unidad.")
 faltantes=[x for x in DOMINIOS if not isinstance(d.get(x),dict)]
 if faltantes:raise ValueError("Faltan dominios: "+", ".join(faltantes)+".")
 c,p,co,pr,i,f,t,a,po=(d[x] for x in DOMINIOS)
 hallazgos=[]
 def agregar(codigo,dominio,detalle):hallazgos.append({"codigo":codigo,"dominio":dominio,"detalle":detalle})
 producto=_entero(c.get("producto_id"),"catalogo.producto_id",1);costo=_entero(c.get("costo_unitario_centavos"),"catalogo.costo_unitario_centavos");precio=_entero(c.get("precio_unitario_centavos"),"catalogo.precio_unitario_centavos",1);sku=str(c.get("sku") or "").strip()
 pedido_id=_entero(p.get("pedido_id"),"pedido.pedido_id",1);cantidad=_entero(p.get("cantidad"),"pedido.cantidad",1);total=_entero(p.get("total_centavos"),"pedido.total_centavos")
 if not sku:agregar("sku_faltante","catalogo","El producto no tiene SKU.")
 if _entero(p.get("producto_id"),"pedido.producto_id",1)!=producto:agregar("producto_pedido_inconsistente","pedido","El pedido no referencia el producto del catalogo.")
 if total!=precio*cantidad:agregar("total_pedido_inconsistente","pedido","El total no coincide con precio por cantidad.")
 compra=_entero(co.get("importe_insumos_centavos"),"compras.importe_insumos_centavos")
 plan=_entero(pr.get("cantidad_planificada"),"produccion.cantidad_planificada",1);buena=_entero(pr.get("cantidad_buena"),"produccion.cantidad_buena");rechazada=_entero(pr.get("cantidad_rechazada"),"produccion.cantidad_rechazada");costo_resultado=_entero(pr.get("costo_resultado_centavos"),"produccion.costo_resultado_centavos")
 if _entero(pr.get("producto_id"),"produccion.producto_id",1)!=producto:agregar("producto_produccion_inconsistente","produccion","La orden no corresponde al producto del catalogo.")
 if buena+rechazada>plan:agregar("avance_supera_plan","produccion","La produccion informada supera la cantidad planificada.")
 if costo_resultado!=costo*buena:agregar("costeo_resultado_inconsistente","produccion","El costo del resultado no coincide con costo unitario por unidades buenas.")
 if costo_resultado>compra:agregar("produccion_supera_compras","compras","El costo del resultado supera los insumos comprados del escenario.")
 inicial=_entero(i.get("stock_inicial"),"inventario.stock_inicial");producido=_entero(i.get("producido"),"inventario.producido");despachado=_entero(i.get("despachado"),"inventario.despachado");reservado=_entero(i.get("reservado_final"),"inventario.reservado_final");final=_entero(i.get("stock_final"),"inventario.stock_final")
 if producido!=buena:agregar("produccion_inventario_inconsistente","inventario","El producido no coincide con unidades buenas.")
 if final!=inicial+producido-despachado:agregar("ecuacion_stock_invalida","inventario","Stock final no coincide con inicial mas producido menos despachado.")
 if reservado>final:agregar("reserva_supera_stock","inventario","La reserva final supera el stock final.")
 if despachado>cantidad:agregar("despacho_supera_pedido","inventario","Se despacho mas que la cantidad pedida.")
 if _entero(f.get("pedido_id"),"facturacion.pedido_id",1)!=pedido_id:agregar("factura_pedido_inconsistente","facturacion","El borrador fiscal no referencia el pedido.")
 if _entero(f.get("total_borrador_centavos"),"facturacion.total_borrador_centavos")!=total:agregar("factura_total_inconsistente","facturacion","El borrador fiscal no coincide con la venta.")
 if bool(f.get("emitida")):agregar("factura_real_emitida","facturacion","El escenario no admite emision real.")
 ingreso=_entero(t.get("ingreso_proyectado_centavos"),"tesoreria.ingreso_proyectado_centavos")
 if ingreso!=total:agregar("tesoreria_inconsistente","tesoreria","El ingreso proyectado no coincide con la venta.")
 if bool(t.get("cobrado")):agregar("cobro_real_registrado","tesoreria","El escenario no admite cobros reales.")
 debe=_entero(a.get("debe_centavos"),"contabilidad.debe_centavos");haber=_entero(a.get("haber_centavos"),"contabilidad.haber_centavos")
 if debe!=haber:agregar("asiento_desbalanceado","contabilidad","Debe y haber no coinciden.")
 if debe!=total:agregar("asiento_importe_inconsistente","contabilidad","El borrador contable no coincide con la venta.")
 if bool(a.get("contabilizado")):agregar("asiento_real_contabilizado","contabilidad","El escenario no admite registracion oficial.")
 afectada=_entero(po.get("cantidad_afectada"),"postventa.cantidad_afectada");exposicion=_entero(po.get("exposicion_centavos"),"postventa.exposicion_centavos")
 if _entero(po.get("pedido_id"),"postventa.pedido_id",1)!=pedido_id:agregar("postventa_pedido_inconsistente","postventa","El caso no referencia el pedido.")
 if afectada>despachado:agregar("postventa_supera_despacho","postventa","La cantidad afectada supera lo despachado.")
 if exposicion>total:agregar("exposicion_supera_venta","postventa","La exposicion supera el total vendido.")
 if bool(po.get("ejecutada")):agregar("postventa_ejecutada","postventa","El escenario no admite efectos de postventa.")
 estados={x:"aprobado" for x in DOMINIOS}
 for h in hallazgos:estados[h["dominio"]]="revisar"
 r={"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),"modo":"aceptacion_operativa_integral_offline","aprobado":not hallazgos,"dominios":[{"dominio":x,"estado":estados[x]} for x in DOMINIOS],"resumen":{"dominios":len(DOMINIOS),"aprobados":sum(v=="aprobado" for v in estados.values()),"hallazgos":len(hallazgos),"venta_centavos":total,"costo_resultado_centavos":costo_resultado,"margen_bruto_centavos":total-costo_resultado},"hallazgos":hallazgos,"controles":{"persistencia":False,"pedidos_creados":0,"stock_movido":0,"facturas_emitidas":0,"cobros":0,"pagos":0,"asientos_contabilizados":0,"acciones_postventa":0,"conexiones_externas":0}}
 r["huella_aceptacion"]=hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest();return r
def exportar(r):return io.BytesIO(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))

