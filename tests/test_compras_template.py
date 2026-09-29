"""La plantilla de Compras debe compilar con filtros estándar de Jinja."""
from pathlib import Path
from jinja2 import Environment, DictLoader


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
