from pathlib import Path


def test_boton_correccion_etiqueta_conserva_texto_blanco():
    plantilla = Path("templates/detalle_pedido.html").read_text(encoding="utf-8")
    estilos = Path("static/style.css").read_text(encoding="utf-8")
    assert "btn-corregir-etiqueta" in plantilla
    assert "a.btn-corregir-etiqueta:visited" in estilos
    bloque = estilos.split(".btn-corregir-etiqueta,", 1)[1].split("}", 1)[0]
    assert "color: #ffffff !important;" in bloque
