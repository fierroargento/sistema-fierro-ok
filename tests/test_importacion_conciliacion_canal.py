from pathlib import Path

from services.importacion_conciliacion_canal import (
    aplicar,
    campos_para,
    previsualizar_movimientos,
    previsualizar_ventas,
    sugerir_mapeo,
)


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


class Campo:
    def __eq__(self, _otro): return self
    def ilike(self, _otro): return self


class Query:
    def __init__(self, filas): self.filas = filas
    def filter_by(self, **filtros): return Query([f for f in self.filas if all(getattr(f, k, None) == v for k, v in filtros.items())])
    def filter(self, *_args): return self
    def first(self): return self.filas[0] if self.filas else None
    def all(self): return list(self.filas)
    def get(self, identificador): return next((f for f in self.filas if getattr(f, "id", None) == identificador), None)


class Lista: pass
class Catalogo: pass
class Inclusion:
    catalogo_id = Campo(); sku_comercial = Campo()
class Venta: pass
class Movimiento: pass
class ReglaCanal: pass
class ReglaEconomica:
    organizacion_id = Campo()
class Costo: pass


def modelos(ventas=None, movimientos=None):
    inclusion = Obj(id=11, catalogo_id=4, producto_id=7, sku_comercial="SKU-001")
    regla_canal = Obj(id=8, lista_precio_id=3, vigente=True, comision_pct=10, umbral_envio_centavos=0, costo_envio_default_centavos=0, tramos=[])
    regla_economica = Obj(vigente=True, clave_alcance="organizacion", impuesto_pct=0, metodo_impuesto="sobre_costo", utilidad_minima_pct=20, utilidad_objetivo_pct=20, metodo_utilidad="sobre_costo", incremento_redondeo_centavos=1)
    Lista.query = Query([Obj(id=3, organizacion_id=1, unidad_negocio_id=2, codigo="canal")])
    Catalogo.query = Query([Obj(id=4, organizacion_id=1, unidad_negocio_id=2, codigo="catalogo")])
    Inclusion.query = Query([inclusion]); Venta.query = Query(ventas or []); Movimiento.query = Query(movimientos or [])
    ReglaCanal.query = Query([regla_canal]); ReglaEconomica.query = Query([regla_economica])
    Costo.query = Query([Obj(organizacion_id=1, unidad_negocio_id=2, producto_id=7, vigente=True, costo_total_centavos=100000)])
    return {"ListaPrecio": Lista, "Catalogo": Catalogo, "CatalogoProducto": Inclusion, "VentaCanalItem": Venta, "MovimientoLiquidacionCanal": Movimiento, "ReglaCanalVersion": ReglaCanal, "ReglaEconomicaVersion": ReglaEconomica, "CostoProductoVersion": Costo}


def test_ventas_y_movimientos_tienen_plantillas_separadas_y_automapeo():
    assert "precio_unitario" in campos_para("ventas")
    assert "referencia_movimiento" in campos_para("movimientos")
    for tipo in ("ventas", "movimientos"):
        encabezados = [d["nombre"] for d in campos_para(tipo).values()]
        assert len([v for v in sugerir_mapeo(encabezados, tipo).values() if v]) == len(encabezados)


def test_venta_valida_congela_costo_y_piso_del_sistema():
    encabezados = [d["nombre"] for d in campos_para("ventas").values()]
    valores = ["canal", "catalogo", "SKU-001", "CUENTA-1", "VENTA-1", "ITEM-1", "PAGO-1", 2, "1.500,00", "confirmada", "04/09/2026 10:00"]
    vista = previsualizar_ventas([{"numero": 2, "valores": valores}], sugerir_mapeo(encabezados, "ventas"), organizacion_id=1, unidad_negocio_id=2, modelos=modelos())
    assert vista[0]["accion"] == "crear"
    assert vista[0]["datos"]["precio_unitario_centavos"] == 150000
    assert vista[0]["datos"]["costo_unitario_centavos"] == 100000
    assert vista[0]["datos"]["piso_unitario_centavos"] == 120000


def test_movimiento_huerfano_o_con_pago_distinto_se_rechaza():
    venta = Obj(
        organizacion_id=1,
        unidad_negocio_id=2,
        cuenta_codigo="CUENTA-1",
        referencia_venta="VENTA-1",
        referencia_item="ITEM-1",
        referencia_pago="PAGO-1",
    )
    encabezados = [d["nombre"] for d in campos_para("movimientos").values()]
    mapeo = sugerir_mapeo(encabezados, "movimientos")
    base = ["CUENTA-1", "VENTA-1", "PAGO-OTRO", "MOV-1", "liquidacion_neta", "credito", 1000, "SI", "confirmado", "05/09/2026", ""]
    vista = previsualizar_movimientos([{"numero": 2, "valores": base}], mapeo, organizacion_id=1, unidad_negocio_id=2, modelos=modelos([venta]))
    assert vista[0]["accion"] == "rechazado"
    assert any("pago no coincide" in error for error in vista[0]["errores"])
    base[1] = "VENTA-INEXISTENTE"; base[2] = ""
    vista = previsualizar_movimientos([{"numero": 3, "valores": base}], mapeo, organizacion_id=1, unidad_negocio_id=2, modelos=modelos([venta]))
    assert any("No existe la venta" in error for error in vista[0]["errores"])


class Sesion:
    def __init__(self): self.agregados = []; self.commits = 0; self.rollbacks = 0
    def add(self, objeto): self.agregados.append(objeto)
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def test_aplicacion_de_movimientos_es_transaccional_y_desconectada():
    sesion = Sesion(); datos = {"cuenta_codigo": "CUENTA-1", "referencia_venta": "VENTA-1", "referencia_pago": "PAGO-1", "referencia_movimiento": "MOV-1", "tipo": "liquidacion_neta", "direccion": "credito", "importe_centavos": 120000, "impacta_saldo": True, "estado": "confirmado", "fecha_movimiento": "2026-09-05T10:00:00", "detalle": None}
    resultado = aplicar([{"accion": "crear", "datos": datos}], "movimientos", organizacion_id=1, unidad_negocio_id=2, usuario=Obj(), modelos={"MovimientoLiquidacionCanal": Obj}, db_session=sesion)
    assert resultado["creados"] == 1 and sesion.commits == 1
    assert sesion.agregados[0].origen == "importacion"


def test_rutas_vista_y_servicio_no_contienen_conectores_externos():
    servicio = Path("services/importacion_conciliacion_canal.py").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_importacion_conciliacion.html").read_text(encoding="utf-8")
    assert "/admin/comercial/conciliacion/importar/<tipo>" in rutas
    assert "Se vuelve a validar antes de confirmar" in panel
    assert "No consulta canales" in panel
    for prohibido in ("requests", "OAuth", "Webhook", "access_token", "mercadopago", "mercadolibre", "tiendanube"):
        assert prohibido not in servicio.lower()
