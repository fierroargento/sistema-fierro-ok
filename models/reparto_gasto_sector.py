"""Reparto versionado de un gasto; la obligación conserva su responsable."""
from sqlalchemy import text
from extensions import db
from services.fechas import ahora_utc_naive

class RepartoGastoSector(db.Model):
    __tablename__ = 'reparto_gasto_sector'
    id = db.Column(db.Integer, primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False)
    costo_fijo_id = db.Column(db.Integer, db.ForeignKey('costo_fijo_productivo.id'), nullable=False)
    numero_revision = db.Column(db.Integer, nullable=False)
    filas = db.Column(db.JSON, nullable=False)
    vigente = db.Column(db.Boolean, nullable=False, default=True)
    creado_por_usuario_id = db.Column(db.Integer)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=ahora_utc_naive)
    __table_args__ = (
        db.UniqueConstraint('costo_fijo_id', 'numero_revision', name='uq_reparto_sector_revision'),
        db.Index('uq_reparto_sector_vigente','costo_fijo_id',unique=True,
            postgresql_where=text('vigente IS TRUE'),sqlite_where=text('vigente IS TRUE')),
    )
