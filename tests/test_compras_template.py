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
