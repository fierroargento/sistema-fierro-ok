from pathlib import Path
from types import SimpleNamespace

from modules.whatsapp import media_inbound
from services.migraciones_saas import (
    asegurar_unidad_tenant_media_whatsapp_preparatoria,
)


class _SessionFake:
    def __init__(self):
        self.agregados = []
        self.sentencias = []
        self.commits = 0

    def add(self, registro):
        self.agregados.append(registro)

    def execute(self, sentencia):
        self.sentencias.append(str(sentencia))

    def commit(self):
        self.commits += 1


class _DbFake:
    engine = object()

    def __init__(self):
        self.session = _SessionFake()


class _InspectorFake:
    def __init__(self, columnas):
        self.columnas = columnas

    def get_table_names(self):
        return ["whatsapp_media_recibida"]

    def get_columns(self, _tabla):
        return [{"name": nombre} for nombre in self.columnas]


class _MediaFake:
    def __init__(self, **valores):
        self.__dict__.update(valores)


def test_media_nueva_persiste_organizacion_y_unidad_sin_red(monkeypatch):
    monkeypatch.setattr(
        media_inbound,
        "obtener_url_temporal_media_meta",
        lambda _media_id: {
            "url": "https://meta.invalid/temporal",
            "mime_type": "image/png",
            "file_size": 4,
        },
    )
    monkeypatch.setattr(
        media_inbound,
        "descargar_media_meta",
        lambda _url: b"dato",
    )
    monkeypatch.setattr(
        media_inbound,
        "subir_media_inbound_cloudinary",
        lambda *_args, **_kwargs: {
            "url": "/archivos-uat/7/11/wa_inbound/archivo.png",
            "public_id": "local:7:11:wa_inbound:archivo.png",
            "size_bytes": 4,
        },
    )
    db = _DbFake()

    resultado = media_inbound.procesar_media_inbound_whatsapp(
        msg={
            "id": "wamid.tenant",
            "type": "image",
            "image": {"id": "media-1", "mime_type": "image/png"},
        },
        pedido=SimpleNamespace(id=23),
        telefono="5491112345678",
        WhatsAppMediaRecibida=_MediaFake,
        db=db,
        organizacion_id=7,
        unidad_negocio_id=11,
    )

    registro = resultado["registro"]
    assert registro.empresa_id == 7
    assert registro.unidad_negocio_id == 11
    assert registro.pedido_id == 23
    assert db.session.agregados == [registro]
    assert db.session.commits == 1


def test_migracion_media_es_aditiva_nullable_y_sin_backfill():
    db = _DbFake()
    inspector = _InspectorFake(["id", "empresa_id"])

    resultado = asegurar_unidad_tenant_media_whatsapp_preparatoria(
        db=db,
        inspect_fn=lambda _engine: inspector,
        text_fn=lambda sentencia: sentencia,
        logger_fn=None,
    )

    assert resultado == {"columna_creada": True}
    sql = "\n".join(db.session.sentencias)
    assert "ADD COLUMN unidad_negocio_id INTEGER" in sql
    assert "CREATE INDEX IF NOT EXISTS" in sql
    assert "UPDATE whatsapp_media_recibida" not in sql
    assert "NOT NULL" not in sql
    assert "DROP " not in sql
    assert db.session.commits == 1


def test_consulta_detalle_filtra_media_por_tenant_completo():
    fuente = Path("app.py").read_text(encoding="utf-8-sig")
    inicio = fuente.index("medias_recibidas = (")
    fin = fuente.index("whatsapp_media_por_message_id = {", inicio)
    bloque = fuente[inicio:fin]

    assert "WhatsAppMediaRecibida.pedido_id == pedido.id" in bloque
    assert (
        "WhatsAppMediaRecibida.empresa_id == pedido.organizacion_id"
        in bloque
    )
    assert (
        "WhatsAppMediaRecibida.unidad_negocio_id == pedido.unidad_negocio_id"
        in bloque
    )


def test_bootstrap_prepara_migracion_sin_ejecutarla_al_importar():
    fuente = Path("services/bootstrap_base_datos.py").read_text(
        encoding="utf-8-sig"
    )
    assert "asegurar_unidad_tenant_media_whatsapp_preparatoria" in fuente
