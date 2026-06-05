from datetime import datetime


def crear_modelo_respuesta_rapida_wa(db):
    """
    Factory de modelo para evitar circular imports con app.py.

    SaaS/CRM:
    - empresa_id queda desde el inicio.
    - imagen opcional queda prevista desde el inicio.
    - la lógica de negocio no vive acá.
    """

    class RespuestaRapidaWA(db.Model):
        __tablename__ = "respuesta_rapida_wa"

        id = db.Column(db.Integer, primary_key=True)
        empresa_id = db.Column(db.Integer, default=1, index=True)

        titulo = db.Column(db.String(120), nullable=False)
        texto = db.Column(db.Text, nullable=False)

        categoria = db.Column(db.String(80), default="General", index=True)
        orden = db.Column(db.Integer, default=100, index=True)
        activa = db.Column(db.Boolean, default=True, index=True)

        imagen_url = db.Column(db.String(500))
        imagen_public_id = db.Column(db.String(255))
        imagen_nombre = db.Column(db.String(255))

        creado_por = db.Column(db.String(100))
        creado_en = db.Column(db.DateTime, default=datetime.utcnow)
        actualizado_en = db.Column(
            db.DateTime,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
        )

    return RespuestaRapidaWA