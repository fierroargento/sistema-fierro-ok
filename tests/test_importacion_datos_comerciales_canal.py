from datetime import datetime
from pathlib import Path

from services.control_comercial_masivo import construir_bandeja
from services.importacion_datos_comerciales_canal import (
    aplicar,
    campos_para,
    previsualizar,
    sugerir_mapeo,
)


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


class Campo:
    def __eq__(self, _otro): return self
    def ilike(self, _otro): return self


class Query:
    def __init__(self, filas): self.filas = filas
    def filter_by(self, **filtros):
        return Query([fila for fila in self.filas if all(getattr(fila, clave, None) == valor for clave, valor in filtros.items())])
    def filter(self, *_args): return self
    def first(self): return self.filas[0] if self.filas else None
    def all(self): return list(self.filas)


class Lista: pass
class Catalogo: pass
class Inclusion:
    catalogo_id = Campo(); sku_comercial = Campo()


def modelos_base():
    lista = Obj(id=3, organizacion_id=1, unidad_negocio_id=2, codigo="canal-principal")
    catalogo = Obj(id=4, organizacion_id=1, unidad_negocio_id=2, codigo="catalogo-general")
    inclusion = Obj(id=11, catalogo_id=4, sku_comercial="SKU-001")
    Lista.query = Query([lista]); Catalogo.query = Query([catalogo]); Inclusion.query = Query([inclusion])
    return {"ListaPrecio": Lista, "Catalogo": Catalogo, "CatalogoProducto": Inclusion}


def fila_valores(valores, numero=2): return {"numero": numero, "valores": valores}


def test_cada_seccion_tiene_contrato_independiente_y_automapeo():
    for tipo, especifico in (("precios", "precio_publicado"), ("promociones", "precio_promocional"), ("cargos", "cargo_fijo"), ("envios", "costo_envio")):
        campos = campos_para(tipo)
        assert especifico in campos
        encabezados = [definicion["nombre"] for definicion in campos.values()]
        assert especifico in sugerir_mapeo(encabezados, tipo).values()


def test_vista_previa_resuelve_tenant_lista_catalogo_producto_y_cuenta():
    encabezados = ["Codigo de lista", "Codigo de catalogo", "SKU comercial", "Cuenta del canal", "Referencia publicacion", "Precio publicado"]
    mapeo = sugerir_mapeo(encabezados, "precios")
    vista = previsualizar(
        [fila_valores(["canal-principal", "catalogo-general", "SKU-001", "cuenta-01", "PUB-1", "1.500,25"])],
        mapeo, "precios", organizacion_id=1, unidad_negocio_id=2, modelos=modelos_base(),
    )
    assert vista[0]["accion"] == "crear_observacion"
    assert vista[0]["lista_id"] == 3 and vista[0]["inclusion_id"] == 11
    assert vista[0]["datos"]["precio_publicado_centavos"] == 150025


def test_filas_duplicadas_y_promociones_incoherentes_se_rechazan():
    encabezados = [d["nombre"] for d in campos_para("promociones").values()]
    mapeo = sugerir_mapeo(encabezados, "promociones")
    valores = ["canal-principal", "catalogo-general", "SKU-001", "cuenta-01", "PUB-1", "Oferta", 1000, 1100, "activa"]
    vista = previsualizar([fila_valores(valores), fila_valores(valores, 3)], mapeo, "promociones", organizacion_id=1, unidad_negocio_id=2, modelos=modelos_base())
    assert vista[0]["accion"] == "rechazado"
    assert any("supera" in error for error in vista[0]["errores"])
    assert any("duplicada" in error for error in vista[1]["errores"])


class Sesion:
    def __init__(self): self.agregados = []; self.commits = 0; self.rollbacks = 0
    def add(self, objeto): self.agregados.append(objeto)
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def test_aplicacion_crea_observaciones_sin_modificar_reglas():
    sesion = Sesion(); modelos = modelos_base()
    modelos.update({"ObservacionComercialCanal": Obj, "PromocionCanalObservacion": Obj})
    vista = [{"accion": "crear_observacion", "lista_id": 3, "inclusion_id": 11, "datos": {"cuenta_codigo": "cuenta-01", "referencia_publicacion": "PUB-1", "precio_publicado_centavos": 150000}}]
    resultado = aplicar(vista, "precios", organizacion_id=1, unidad_negocio_id=2, lote_id=8, usuario=Obj(id=9, username="admin"), modelos=modelos, db_session=sesion)
    assert resultado["creados"] == 1 and sesion.commits == 1
    assert sesion.agregados[0].tipo == "precio"
    assert sesion.agregados[0].origen == "importacion"


def test_precio_importado_pasa_a_ser_precio_efectivo_del_control():
    simulacion = {
        "costo": Obj(producto_id=7, producto=Obj(sku="SKU-001")), "inclusion": Obj(id=11),
        "regla_canal": Obj(lista_precio_id=3, lista_precio=Obj(nombre="Canal"), comision_pct=10, umbral_envio_centavos=0, costo_envio_default_centavos=0, tramos=[]),
        "minimo": {"precio_final_centavos": 100000, "piso_liquidacion_centavos": 90000},
        "objetivo": {"precio_final_centavos": 120000, "piso_liquidacion_centavos": 108000},
    }
    observacion = Obj(lista_precio_id=3, catalogo_producto_id=11, tipo="precio", precio_publicado_centavos=110000, fecha_observacion=datetime(2026, 9, 4))
    filas, _ = construir_bandeja([simulacion], [], [], [observacion])
    assert filas[0]["fuente_precio"] == "precio_importado"
    assert filas[0]["actual"]["precio_final_centavos"] == 110000


def test_rutas_plantillas_y_servicio_permanecen_desconectados():
    servicio = Path("services/importacion_datos_comerciales_canal.py").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    plantilla = Path("templates/admin_importacion_datos_canal.html").read_text(encoding="utf-8")
    assert "/admin/comercial/importaciones/datos-canal/<tipo>" in rutas
    assert "Precios publicados" in panel and "Comisiones y cargos" in panel
    assert "No actualiza publicaciones" in plantilla
    for prohibido in ("requests", "OAuth", "Webhook", "MercadoLibre", "access_token"):
        assert prohibido not in servicio
