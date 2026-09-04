import json
from pathlib import Path

import pytest

from services.preparacion_integracion_canal import (
    contrato_evento, guardar_control, matriz_preparacion,
    procesar_evento_simulado, registrar_evento,
)


class Obj:
    query = None
    def __init__(self, **datos): self.__dict__.update(datos)


class Query:
    def __init__(self, filas): self.filas = filas
    def filter_by(self, **filtros): return Query([fila for fila in self.filas if all(getattr(fila, clave, None) == valor for clave, valor in filtros.items())])
    def first(self): return self.filas[0] if self.filas else None


class Sesion:
    def __init__(self): self.agregados = []; self.commits = 0
    def add(self, objeto): self.agregados.append(objeto)
    def commit(self): self.commits += 1


def control(**cambios):
    datos = dict(id=3, organizacion_id=1, unidad_negocio_id=2, canal="mercado_libre", cuenta_codigo="cuenta-1", modo="simulacion", recepcion_externa_habilitada=False, acciones_externas_habilitadas=False, certificacion_interna_aprobada=True)
    datos.update(cambios); return Obj(**datos)


def test_control_siempre_conserva_bloqueadas_las_conexiones():
    Obj.query = Query([]); sesion = Sesion()
    creado = guardar_control(
        organizacion_id=1, unidad_negocio_id=2, canal="mercado_pago",
        cuenta_codigo="PAGOS-1", modo="simulacion", certificacion_aprobada=True,
        usuario=Obj(id=9, username="admin"), ControlIntegracionCanal=Obj, db_session=sesion,
    )
    assert creado.recepcion_externa_habilitada is False
    assert creado.acciones_externas_habilitadas is False
    assert sesion.commits == 1


def test_contrato_normaliza_siete_tipos_de_evento():
    for tipo in ("publicacion", "comision", "envio", "promocion", "venta", "pago", "devolucion"):
        assert contrato_evento(tipo, "REF-1", {"valor": 1})["version_esquema"] == 1


def test_staging_es_idempotente_por_cuenta_tipo_y_referencia():
    sesion = Sesion(); Obj.query = Query([]); configuracion = control()
    evento, creado = registrar_evento(
        control=configuracion, tipo_evento="venta", referencia_evento="VENTA-1",
        datos={"importe": 1000}, origen="simulacion", usuario=Obj(username="admin"),
        EventoIntegracionStaging=Obj, db_session=sesion,
    )
    assert creado and len(evento.payload_hash) == 64
    Obj.query = Query([evento])
    repetido, creado = registrar_evento(
        control=configuracion, tipo_evento="venta", referencia_evento="VENTA-1",
        datos={"importe": 9999}, origen="simulacion",
        EventoIntegracionStaging=Obj, db_session=sesion,
    )
    assert repetido is evento and creado is False and len(sesion.agregados) == 1


def test_solo_evento_validado_puede_aplicarse_como_simulacion():
    sesion = Sesion(); configuracion = control()
    sobre = contrato_evento("pago", "PAGO-1", {"importe": 850})
    evento = Obj(origen="simulacion", estado="recibido", control=configuracion, payload_json=json.dumps(sobre), error_validacion=None)
    with pytest.raises(ValueError): procesar_evento_simulado(evento, "aplicar_simulado", db_session=sesion)
    procesar_evento_simulado(evento, "validar", db_session=sesion)
    procesar_evento_simulado(evento, "aplicar_simulado", db_session=sesion)
    assert evento.estado == "aplicado_simulado"


def test_origen_externo_y_modo_deshabilitado_se_rechazan():
    Obj.query = Query([])
    with pytest.raises(ValueError, match="pruebas internas"):
        registrar_evento(control=control(modo="deshabilitado"), tipo_evento="venta", referencia_evento="1", datos={}, origen="manual", EventoIntegracionStaging=Obj, db_session=Sesion())
    with pytest.raises(ValueError, match="manuales o simulados"):
        registrar_evento(control=control(), tipo_evento="venta", referencia_evento="1", datos={}, origen="externo", EventoIntegracionStaging=Obj, db_session=Sesion())


def test_matriz_nunca_habilita_conexion_real():
    matriz = matriz_preparacion(control(), costos=2, reglas_economicas=1, reglas_canal=1, identidades=3, validaciones=1)
    assert matriz["apto_pruebas_internas"] is True
    assert matriz["conexion_real_habilitada"] is False
    incompleta = matriz_preparacion(control(certificacion_interna_aprobada=False), costos=0, reglas_economicas=1, reglas_canal=1, identidades=0, validaciones=1)
    assert set(incompleta["faltantes"]) == {"costos_vigentes", "identidades_publicacion", "certificacion_interna"}


def test_panel_y_servicio_no_implementan_transporte_externo():
    servicio = Path("services/preparacion_integracion_canal.py").read_text(encoding="utf-8").lower()
    panel = Path("templates/admin_preparacion_integraciones.html").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    assert "/admin/comercial/preparacion-integraciones" in rutas
    assert "Bloqueo externo obligatorio" in panel and "Aplicar simulado" in panel
    for prohibido in ("requests", "oauth", "webhook", "access_token", "http://", "https://"):
        assert prohibido not in servicio
