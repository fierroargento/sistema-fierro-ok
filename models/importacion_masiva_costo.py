"""Lotes temporales e historial de importaciones de costos."""

from sqlalchemy import CheckConstraint

from extensions import db
from services.fechas import ahora_utc_naive


class ImportacionMasivaCosto(db.Model):
    __tablename__ = "importacion_masiva_costo"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('cargado', 'mapeado', 'confirmado', 'cancelado', 'error')",
            name="ck_importacion_masiva_costo_estado",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(
        db.Integer, db.ForeignKey("organizacion.id"), nullable=False, index=True,
    )
    unidad_negocio_id = db.Column(
        db.Integer, db.ForeignKey("unidad_negocio.id"), nullable=True, index=True,
    )
    usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario_sistema.id"), nullable=True, index=True,
    )
    tipo_datos = db.Column(db.String(50), nullable=False, index=True)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    nombre_hoja = db.Column(db.String(150))
    estado = db.Column(db.String(20), default="cargado", nullable=False, index=True)
    modo = db.Column(db.String(20), default="crear_actualizar", nullable=False)
    encabezados_json = db.Column(db.Text, nullable=False)
    filas_json = db.Column(db.Text, nullable=False)
    mapeo_json = db.Column(db.Text)
    vista_previa_json = db.Column(db.Text)
    total_filas = db.Column(db.Integer, default=0, nullable=False)
    creados = db.Column(db.Integer, default=0, nullable=False)
    actualizados = db.Column(db.Integer, default=0, nullable=False)
    sin_cambios = db.Column(db.Integer, default=0, nullable=False)
    rechazados = db.Column(db.Integer, default=0, nullable=False)
    detalle_error = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    fecha_confirmacion = db.Column(db.DateTime)

    unidad_negocio = db.relationship("UnidadNegocio")
