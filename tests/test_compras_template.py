"""La plantilla de Compras debe compilar con filtros estándar de Jinja."""
from pathlib import Path
from jinja2 import Environment, DictLoader, FileSystemLoader


def test_compras_compila_sin_filtros_personalizados():
    template = Path(__file__).resolve().parents[1] / "templates/admin_compras.html"
    environment = Environment(loader=DictLoader({
        "admin_compras.html": template.read_text(),
        "base.html": "{% block content %}{% endblock %}",
    }))
    environment.get_template("admin_compras.html")


def test_cantidad_preserva_precision_y_elimina_ceros_finales():
    template = Environment().from_string(
        "{{ ('%.6f'|format(cantidad|float)).rstrip('0').rstrip('.') }}"
    )
    assert template.render(cantidad="2.000000") == "2"
    assert template.render(cantidad="0.123456") == "0.123456"
    assert template.render(cantidad="0.000000") == "0"


def test_cola_obsoleta_oculta_confirmacion_y_ofrece_archivo():
    from types import SimpleNamespace as O
    fuente=Path("templates/admin_comercial.html").read_text()
    fragmento=fuente[fuente.index('<div id="cola-comercial"'):fuente.index('\n  </section>',fuente.index('<div id="cola-comercial"'))]
    p=O(id=9,orden=1,estado="aprobada",tipo_accion="actualizar_precio",precio_actual_centavos=600000,precio_propuesto_centavos=712500,depende_de=None,catalogo_producto=O(producto=O(sku="UAT")),lista_precio=O(nombre="UAT"))
    html=Environment().from_string(fragmento).render(propuestas_comerciales=[p],propuestas_obsoletas=[9],url_for=lambda *a,**k:"/decision")
    assert "Obsoleta" in html and "Archivar obsoleta" in html
    assert "Confirmar gestión manual" not in html and 'value="aprobar"' not in html


def test_ficha_proveedor_renderiza_datos_y_conserva_edicion_segura():
    from types import SimpleNamespace as O
    from html.parser import HTMLParser
    source = Path("templates/admin_compras.html").read_text()
    start = source.index('<section id="compras-proveedores"')
    end = source.rfind('</section>', start, source.index('<section id="compras-ordenes"', start)) + len('</section>')
    supplier = O(id=1, codigo="UAT-001", razon_social='Proveedor <UAT>', cuit="30700000001",
                 estado="activo", persona_contacto="Contacto", email="uat@example.invalid",
                 telefono="123", domicilio="Calle 123", localidad="Viedma", provincia="Río Negro",
                 codigo_postal="8500", observacion='Nota <script>sin ejecutar</script>')
    html = Environment(autoescape=True, loader=FileSystemLoader('templates')).from_string(source[start:end]).render(
        unidad_activa=O(id=1,nombre="Unidad de prueba"),
        proveedores=[supplier], organizacion=O(nombre="UAT"), csrf_token_value="token-UAT",
        contactos_proveedores={1: "456"}, contactos_preparados=True,
        url_for=lambda *a, **k: "/guardar")
    class Controls(HTMLParser):
        def __init__(self):
            super().__init__()
            self.inputs = []
            self.scripts = 0
            self.summaries = []
            self.current_summary = None
        def handle_starttag(self, tag, attrs):
            if tag == "input":
                self.inputs.append(dict(attrs))
            if tag == "script":
                self.scripts += 1
            if tag == "summary":
                self.current_summary = {"attrs": dict(attrs), "text": ""}
        def handle_data(self, data):
            if self.current_summary is not None:
                self.current_summary["text"] += data
        def handle_endtag(self, tag):
            if tag == "summary" and self.current_summary is not None:
                self.summaries.append(self.current_summary)
                self.current_summary = None
    dom = Controls()
    dom.feed(html)
    actions = {s['text'].strip(): s['attrs'].get('data-fierro-icon') for s in dom.summaries}
    assert actions['Gestionar'] == 'gestionar'
    for title in ("Datos fiscales", "Contacto", "Domicilio", "Observaciones"):
        assert f"<h3>{title}</h3>" in html
    assert "30700000001" in html and "Calle 123" in html
    assert actions['Editar proveedor'] == 'gestionar'
    def value(name):
        return next(i["value"] for i in dom.inputs if i.get("name") == name and "value" in i)
    assert value("proveedor_id") == "1"
    assert value("_csrf_token") == "token-UAT"
    assert value("razon_social") == "Proveedor <UAT>"
    assert value("telefono_contacto") == "456"
    assert not dom.scripts
