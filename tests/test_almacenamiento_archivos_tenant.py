from io import BytesIO
from pathlib import Path

from PIL import Image
import pytest

from services import almacenamiento_archivos
from services import comprobantes_pagos_productivos
from modules.whatsapp import respuestas_rapidas


class Archivo:
    def __init__(self, contenido, nombre, mimetype=""):
        self.stream = BytesIO(contenido)
        self.filename = nombre
        self.mimetype = mimetype

    def read(self, *args):
        return self.stream.read(*args)


def png_bytes():
    salida = BytesIO()
    Image.new("RGB", (4, 4), "red").save(salida, format="PNG")
    return salida.getvalue()


def preparar_local(monkeypatch, tmp_path):
    monkeypatch.setenv("ALMACENAMIENTO_ARCHIVOS", "local_aislado")
    monkeypatch.setenv("STAGING_UPLOAD_ROOT", str(tmp_path))


def test_imagenes_quedan_separadas_por_organizacion_y_unidad(monkeypatch, tmp_path):
    preparar_local(monkeypatch, tmp_path)
    primera = almacenamiento_archivos.guardar_imagen_local(
        Archivo(png_bytes(), "producto.png"),
        organizacion_id=1, unidad_negocio_id=10,
        espacio="catalogo_7", limite_bytes=1024 * 1024,
    )
    segunda = almacenamiento_archivos.guardar_imagen_local(
        Archivo(png_bytes(), "producto.png"),
        organizacion_id=1, unidad_negocio_id=20,
        espacio="catalogo_7", limite_bytes=1024 * 1024,
    )

    assert primera["url"].startswith("/archivos-uat/1/10/catalogo_7/")
    assert segunda["url"].startswith("/archivos-uat/1/20/catalogo_7/")
    assert primera["public_id"] != segunda["public_id"]
    assert len(list((tmp_path / "organizacion_1" / "unidad_10").rglob("*.png"))) == 1
    assert len(list((tmp_path / "organizacion_1" / "unidad_20").rglob("*.png"))) == 1


def test_identidad_invalida_y_pdf_falso_se_rechazan(monkeypatch, tmp_path):
    preparar_local(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="organización y unidad"):
        almacenamiento_archivos.guardar_imagen_local(
            Archivo(png_bytes(), "producto.png"),
            organizacion_id=1, unidad_negocio_id=None,
            espacio="catalogo", limite_bytes=1024,
        )
    with pytest.raises(ValueError, match="PDF válido"):
        almacenamiento_archivos.guardar_archivo_local(
            Archivo(b"esto no es pdf", "comprobante.pdf"),
            organizacion_id=1, unidad_negocio_id=10,
            espacio="costos", limite_bytes=1024,
            extensiones_permitidas={"pdf"},
        )


def test_raiz_del_sistema_no_puede_usarse_como_upload_root(monkeypatch):
    monkeypatch.setenv("STAGING_UPLOAD_ROOT", "/")
    with pytest.raises(RuntimeError, match="raíz del sistema"):
        almacenamiento_archivos.raiz_local_aislada()


def test_compensacion_elimina_solo_archivo_del_tenant(monkeypatch, tmp_path):
    preparar_local(monkeypatch, tmp_path)
    guardado = almacenamiento_archivos.guardar_imagen_local(
        Archivo(png_bytes(), "producto.png"),
        organizacion_id=1, unidad_negocio_id=10,
        espacio="catalogo_7", limite_bytes=1024 * 1024,
    )
    assert almacenamiento_archivos.eliminar_archivos_locales(
        [guardado], organizacion_id=1, unidad_negocio_id=10,
    ) == 1
    assert not list(tmp_path.rglob("*.png"))

    assert almacenamiento_archivos.eliminar_archivos_locales(
        [{"public_id": "local:2:10:catalogo_7/ajeno.png"}],
        organizacion_id=1, unidad_negocio_id=10,
    ) == 0


def test_comprobante_costos_local_no_invoca_cloudinary(monkeypatch, tmp_path):
    preparar_local(monkeypatch, tmp_path)
    monkeypatch.setattr(
        comprobantes_pagos_productivos, "exigir_conexion_externa",
        lambda *_args: (_ for _ in ()).throw(AssertionError("intentó red")),
    )
    url = comprobantes_pagos_productivos.guardar_comprobante_pago(
        Archivo(b"%PDF-1.4\nprueba", "pago.pdf"),
        organizacion_id=2, unidad_negocio_id=30,
    )

    assert url.startswith("/archivos-uat/2/30/costos_comprobantes_pago/")
    assert len(list(Path(tmp_path).rglob("*.pdf"))) == 1


def test_imagen_manual_wa_local_no_invoca_cloudinary(monkeypatch, tmp_path):
    preparar_local(monkeypatch, tmp_path)
    monkeypatch.setattr(
        respuestas_rapidas, "exigir_conexion_externa",
        lambda *_args: (_ for _ in ()).throw(AssertionError("intentó red")),
    )
    resultado = respuestas_rapidas.subir_imagen_manual_wa_cloudinary(
        Archivo(png_bytes(), "consulta.png", "image/png"),
        pedido_id=55, usuario="operador",
        organizacion_id=2, unidad_negocio_id=30,
    )

    assert resultado["url"].startswith(
        "/archivos-uat/2/30/wa_operador_pedido_55/"
    )
    assert resultado["nombre"] == "consulta.png"


def test_cloudinary_requiere_conexion_y_efecto_en_cada_frontera():
    archivos = (
        "app.py",
        "services/catalogo_ficha_integral.py",
        "services/comprobantes_pagos_productivos.py",
        "modules/whatsapp/respuestas_rapidas.py",
        "modules/whatsapp/media_inbound.py",
    )
    for nombre in archivos:
        fuente = Path(nombre).read_text(encoding="utf-8-sig")
        if "cloudinary.uploader.upload" not in fuente:
            continue
        assert 'exigir_conexion_externa("CLOUDINARY"' in fuente
        assert 'exigir_efecto_externo("CLOUDINARY"' in fuente
