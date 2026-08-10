from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as Obj

from services.composicion_costo_producto import construir_detalles, construir_detalles_combo


def test_calcula_insumo_mano_obra_y_fijo_sin_costos_comerciales():
    insumo = Obj(
        codigo="hierro", nombre="Hierro", unidad_medida="kg",
        versiones_precio=[Obj(vigente=True, moneda="ARS", precio_unitario_centavos=1000)],
    )
    empleado = Obj(
        codigo="soldador", nombre="Soldador",
        versiones_costo=[Obj(vigente=True, moneda="ARS", costo_minuto_productivo_centavos=50)],
    )
    fijo = Obj(
        codigo="alquiler", nombre="Alquiler",
        versiones=[Obj(vigente=True, moneda="ARS", importe_mensual_centavos=100000)],
    )
    perfil = Obj(
        tipo="produccion",
        insumos_costeo=[Obj(insumo=insumo, cantidad=Decimal("2"), porcentaje_merma=Decimal("10"), observacion=None)],
        operaciones_costeo=[Obj(empleado=empleado, nombre="Soldadura", minutos=Decimal("5"), orden=0, observacion=None)],
        costos_fijos_costeo=[Obj(costo_fijo=fijo, porcentaje_asignacion=Decimal("20"), unidades_mensuales=Decimal("100"), observacion=None)],
    )
    detalles = construir_detalles(perfil)
    assert [d["tipo"] for d in detalles] == ["insumo", "mano_obra", "elaboracion"]
    assert detalles[2]["costo_unitario_centavos"] == 200
    assert all("comision" not in str(d).lower() for d in detalles)


def test_modelos_y_panel_son_modulares():
    app = Path("app.py").read_text(encoding="utf-8")
    modelo = Path("models/composicion_costo_producto.py").read_text(encoding="utf-8")
    servicio = Path("services/composicion_costo_producto.py").read_text(encoding="utf-8")
    template = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    assert "ProductoInsumoCosteo" in modelo
    assert "ProductoOperacionCosteo" in modelo
    assert "ProductoCostoFijoCosteo" in modelo
    assert "def construir_detalles" in servicio
    assert "def construir_detalles_combo" in servicio
    assert 'id="fichas-tecnicas"' in template
    assert "services.composicion_costo_producto import" not in app


def test_estetica_usa_unidad_activa():
    comercial = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    estilos = Path("static/admin_comercial.css").read_text(encoding="utf-8")
    assert "Ej. {{ unidad_activa.codigo }}" in comercial
    assert "Ej. Catálogo {{ unidad_activa.nombre }}" in comercial
    assert ".form-source-insumo > label:first-of-type" in estilos


def test_listados_productivos_quedan_plegados_y_los_insumos_en_tabla():
    template = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    estilos = Path("static/admin_comercial.css").read_text(encoding="utf-8")

    assert "Ver insumos cargados" in template
    assert "Ver empleados cargados" in template
    assert "Ver costos fijos cargados" in template
    assert "Ver fichas técnicas" in template
    assert "Ver productos clasificados" in template
    assert 'class="table-wrap source-catalog-table"' in template
    assert "Gestionar" in template
    assert "source-table-update" in template
    assert "v='20260810-9'" in template
    assert ".source-catalog > summary" in estilos
    assert ".source-dialog::backdrop" in estilos


def test_fichas_explican_y_bloquean_fuentes_que_aun_no_existen():
    template = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    estilos = Path("static/admin_comercial.css").read_text(encoding="utf-8")

    assert "Primero cargá un insumo productivo" in template
    assert "Primero cargá un empleado o recurso" in template
    assert "No hay costos fijos productivos" in template
    assert "not hay_recursos_laborales %}disabled" in template
    assert "not costos_fijos_productivos %}disabled" in template
    assert ".comercial-primary:disabled" in estilos
    assert ".cost-sheet-forms select:disabled" in estilos


def test_configuracion_laboral_separa_titulo_y_explicacion():
    template = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    estilos = Path("static/admin_comercial.css").read_text(encoding="utf-8")

    assert 'class="labor-general-copy"' in template
    assert ".labor-general-copy {" in estilos
    assert ".labor-general-copy strong," in estilos
    assert "flex-direction:column" in estilos


def test_porcentajes_laborales_no_muestran_ceros_decimales_innecesarios():
    template = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")

    assert "macro numero_decimal_limpio(valor)" in template
    assert ".rstrip('0').rstrip('.')" in template
    assert "numero_decimal_limpio(configuracion_costo_laboral.porcentaje_cargas)" in template
    assert "numero_decimal_limpio(vigente.porcentaje_cargas)" in template


def test_listados_productivos_similares_usan_tablas_y_accion_gestionar():
    template = Path("templates/admin_fuentes_costos.html").read_text(encoding="utf-8")
    estilos = Path("static/admin_comercial.css").read_text(encoding="utf-8")

    assert "<th>Empleado</th>" in template
    assert "<th>Recurso</th>" in template
    assert "<th>Concepto</th>" in template
    assert template.count('class="table-wrap source-catalog-table"') >= 4
    javascript = Path("static/admin_fuentes_costos.js").read_text(encoding="utf-8")
    assert template.count('data-source-dialog') >= 2
    assert 'document.querySelectorAll(".source-row-action")' in javascript
    assert "showModal()" in javascript
    assert "dialogo.close()" in javascript
    assert 'class="source-grid source-grid-wide source-catalog-content"' not in template
    assert 'class="source-grid source-catalog-content"' not in template
    assert ".employee-table-update" in estilos
