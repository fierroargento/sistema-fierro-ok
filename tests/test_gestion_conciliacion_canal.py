from pathlib import Path

import pytest

from services.conciliacion_liquidaciones_canal import (
    clasificar_caso,
    incorporar_gestiones,
    registrar_gestion,
)


class Obj:
    def __init__(self, **datos): self.__dict__.update(datos)


class Sesion:
    def __init__(self): self.agregados = []; self.commits = 0
    def add(self, objeto): self.agregados.append(objeto)
    def commit(self): self.commits += 1


def fila(**cambios):
    datos = {
        "cuenta_codigo": "CUENTA-1", "referencia_venta": "VENTA-1",
        "estado_conciliacion": "pago_parcial", "estado_economico": "cumple",
        "liquidacion_esperada_centavos": 150000, "liquidacion_real_centavos": 120000,
        "diferencia_centavos": -30000,
    }
    datos.update(cambios)
    return datos


def test_clasificacion_prioriza_el_piso_economico():
    assert clasificar_caso(fila()) == "pago_incompleto"
    assert clasificar_caso(fila(estado_economico="bajo_piso")) == "bajo_piso"
    assert clasificar_caso(fila(estado_conciliacion="pendiente")) == "pago_pendiente"


def test_ultima_gestion_se_incorpora_sin_alterar_importes():
    anterior = Obj(id=1, cuenta_codigo="CUENTA-1", referencia_venta="VENTA-1", estado="en_revision", fecha_registro=None)
    ultima = Obj(id=2, cuenta_codigo="CUENTA-1", referencia_venta="VENTA-1", estado="resuelta", fecha_registro=None)
    caso = fila()
    incorporar_gestiones([caso], [ultima, anterior])
    assert caso["gestion_actual"] is ultima
    assert caso["estado_gestion"] == "resuelta"
    assert caso["diferencia_centavos"] == -30000


def test_decision_conserva_snapshot_y_autoria():
    sesion = Sesion()
    registro = registrar_gestion(
        fila(), clasificacion="pago_incompleto", estado="resuelta",
        observacion="Diferencia justificada por retencion.", organizacion_id=1,
        unidad_negocio_id=2, usuario=Obj(id=9, username="admin"),
        GestionConciliacionCanal=Obj, db_session=sesion,
    )
    assert registro.diferencia_snapshot_centavos == -30000
    assert registro.creado_por_username == "admin"
    assert sesion.commits == 1


def test_cierre_exige_observacion_pero_revision_no():
    argumentos = dict(
        clasificacion="pago_incompleto", observacion="", organizacion_id=1,
        unidad_negocio_id=2, usuario=Obj(), GestionConciliacionCanal=Obj,
        db_session=Sesion(),
    )
    with pytest.raises(ValueError, match="observacion"):
        registrar_gestion(fila(), estado="resuelta", **argumentos)
    registrar_gestion(fila(), estado="en_revision", **argumentos)


def test_panel_permite_gestion_masiva_y_filtros():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_conciliacion_canal.html").read_text(encoding="utf-8")
    assert 'accion == "gestionar_casos"' in rutas
    assert 'request.form.getlist("casos")' in rutas
    assert "Requieren revisión" in panel
    assert "Historial de decisiones" in panel


def test_gestion_es_interna_y_no_contiene_conectores():
    textos = "".join(Path(ruta).read_text(encoding="utf-8").lower() for ruta in (
        "models/conciliacion_ventas_canal.py",
        "services/conciliacion_liquidaciones_canal.py",
        "templates/admin_conciliacion_canal.html",
    ))
    for prohibido in ("requests", "oauth", "webhook", "access_token", "mercadopago", "mercadolibre", "tiendanube"):
        assert prohibido not in textos
