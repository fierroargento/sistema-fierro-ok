from io import BytesIO

import pytest
from PIL import Image

from services import documentos_pedido


class Archivo:
    def __init__(self, contenido, nombre, content_type=""):
        self.stream = BytesIO(contenido)
        self.filename = nombre
        self.content_type = content_type

    def read(self, *args):
        return self.stream.read(*args)


def _pdf(nombre="documento.pdf"):
    return Archivo(
        b"%PDF-1.4\ncontenido de prueba",
        nombre,
        "application/pdf",
    )


def _png(nombre="imagen.png"):
    contenido = BytesIO()
    Image.new("RGB", (2, 2), "white").save(contenido, format="PNG")
    contenido.seek(0)
    return Archivo(contenido.getvalue(), nombre, "image/png")


@pytest.mark.parametrize(
    ("tipo", "archivo"),
    [
        ("etiqueta", _pdf),
        ("comprobante_dux", _pdf),
        ("comprobante_pago", _png),
    ],
)
def test_documentos_uat_se_guardan_por_tenant(
    monkeypatch, tmp_path, tipo, archivo,
):
    monkeypatch.setenv("ALMACENAMIENTO_ARCHIVOS", "local_aislado")
    monkeypatch.setenv("STAGING_UPLOAD_ROOT", str(tmp_path))

    resultado = documentos_pedido.guardar_documento_pedido(
        archivo(),
        tipo=tipo,
        organizacion_id=8,
        unidad_negocio_id=13,
        pedido_id=55,
        cloudinary_uploader=None,
    )

    assert resultado["url"].startswith(
        f"/archivos-uat/8/13/pedidos/55/{tipo}/"
    )
    assert resultado["public_id"].startswith("local:8:13:")
    assert list((tmp_path / "organizacion_8" / "unidad_13").rglob("*.*"))


def test_dux_rechaza_archivo_que_no_es_pdf(monkeypatch, tmp_path):
    monkeypatch.setenv("ALMACENAMIENTO_ARCHIVOS", "local_aislado")
    monkeypatch.setenv("STAGING_UPLOAD_ROOT", str(tmp_path))

    with pytest.raises(ValueError, match="PDF válido"):
        documentos_pedido.guardar_documento_pedido(
            Archivo(b"falso", "falso.pdf"),
            tipo="comprobante_dux",
            organizacion_id=1,
            unidad_negocio_id=2,
            pedido_id="nuevo",
        )


def test_referencia_uat_no_puede_cruzar_organizacion_o_unidad(monkeypatch):
    monkeypatch.setenv("ALMACENAMIENTO_ARCHIVOS", "local_aislado")
    propia = "/archivos-uat/8/13/pedidos_55_etiqueta/a.pdf"
    otra_unidad = "/archivos-uat/8/99/pedidos_55_etiqueta/a.pdf"
    otra_organizacion = "/archivos-uat/9/13/pedidos_55_etiqueta/a.pdf"

    assert documentos_pedido.referencia_local_pertenece_tenant(
        propia, organizacion_id=8, unidad_negocio_id=13,
    )
    assert not documentos_pedido.referencia_local_pertenece_tenant(
        otra_unidad, organizacion_id=8, unidad_negocio_id=13,
    )
    assert not documentos_pedido.referencia_local_pertenece_tenant(
        otra_organizacion, organizacion_id=8, unidad_negocio_id=13,
    )
    assert not documentos_pedido.referencia_local_pertenece_tenant(
        propia + "/../secreto", organizacion_id=8, unidad_negocio_id=13,
    )


def test_cloudinary_exige_conexion_y_efecto(monkeypatch):
    monkeypatch.delenv("ALMACENAMIENTO_ARCHIVOS", raising=False)
    llamadas = []
    monkeypatch.setattr(
        documentos_pedido,
        "exigir_conexion_externa",
        lambda *_args: llamadas.append("conexion"),
    )
    monkeypatch.setattr(
        documentos_pedido,
        "exigir_efecto_externo",
        lambda *_args: llamadas.append("efecto"),
    )

    class Uploader:
        def upload(self, _archivo, **kwargs):
            assert kwargs["folder"].startswith(
                "sistema_fierro/8/13/pedidos/55/"
            )
            return {"secure_url": "https://cdn.invalid/a.pdf", "public_id": "a"}

    resultado = documentos_pedido.guardar_documento_pedido(
        _pdf(),
        tipo="comprobante_dux",
        organizacion_id=8,
        unidad_negocio_id=13,
        pedido_id=55,
        cloudinary_uploader=Uploader(),
    )

    assert llamadas == ["conexion", "efecto"]
    assert resultado["public_id"] == "a"


def test_app_no_confia_en_hidden_de_documentos_al_editar():
    fuente = open("app.py", encoding="utf-8-sig").read()
    inicio = fuente.index("def editar_pedido(id):")
    fin = fuente.index("\n@app.route", inicio)
    bloque = fuente[inicio:fin]
    assert 'request.form.get("etiqueta_existente"' not in bloque
    assert 'request.form.get("comprobante_dux_existente"' not in bloque
    assert "guardar_etiqueta_subida(archivo_etiqueta, pedido)" in bloque


def test_alta_manual_asigna_unidad_activa():
    fuente = open("app.py", encoding="utf-8-sig").read()
    inicio = fuente.index("def nuevo_pedido():")
    fin = fuente.index("\n@app.route", inicio)
    bloque = fuente[inicio:fin]
    assert "unidad_pedido = unidad_negocio_actual_o_403" in bloque
    assert "unidad_negocio_id=unidad_pedido.id" in bloque


def test_lecturas_legacy_y_uat_respetan_unidad_y_ruta_aislada():
    fuente = open("app.py", encoding="utf-8-sig").read()
    assert ".filter(Pedido.unidad_negocio_id == unidad_id)" in fuente
    assert 'if etiqueta_referencia.startswith("/archivos-uat/"):' in fuente
    assert 'if etiqueta.startswith("/archivos-uat/"):' in fuente
    template = open(
        "templates/detalle_pedido.html", encoding="utf-8-sig"
    ).read()
    assert 'dux_valor.startswith("/archivos-uat/")' in template
    assert 'etiqueta_valor.startswith("/archivos-uat/")' in template
