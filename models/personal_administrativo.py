"""Ampliación del legajo existente; no crea otra identidad de empleado."""
from sqlalchemy import CheckConstraint, UniqueConstraint
from extensions import db
from services.fechas import ahora_utc_naive


class PersonalDetalle(db.Model):
    __tablename__ = 'personal_detalle'
    empleado_id = db.Column(db.Integer, db.ForeignKey('empleado_productivo.id'), primary_key=True)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'), nullable=False, index=True)
    dni = db.Column(db.String(20))
    cuil = db.Column(db.String(20))
    fecha_nacimiento = db.Column(db.Date)
    fecha_ingreso = db.Column(db.Date)
    fecha_egreso = db.Column(db.Date)
    telefono = db.Column(db.String(40))
    email = db.Column(db.String(200))
    domicilio = db.Column(db.String(300))
    localidad = db.Column(db.String(120))
    provincia = db.Column(db.String(120))
    contacto_emergencia = db.Column(db.String(200))
    categoria = db.Column(db.String(120))
    convenio = db.Column(db.String(160))
    modalidad = db.Column(db.String(120))
    __table_args__ = (UniqueConstraint('organizacion_id','dni',name='uq_personal_dni_org'), UniqueConstraint('organizacion_id','cuil',name='uq_personal_cuil_org'), CheckConstraint('fecha_egreso IS NULL OR fecha_ingreso IS NULL OR fecha_egreso >= fecha_ingreso', name='ck_personal_fechas_ingreso'),)


class HorarioPersonal(db.Model):
    __tablename__ = 'horario_personal'
    id = db.Column(db.Integer, primary_key=True)
    empleado_id = db.Column(db.Integer, db.ForeignKey('empleado_productivo.id'), nullable=False, index=True)
    dia_semana = db.Column(db.Integer, nullable=False)
    entrada = db.Column(db.Time, nullable=False)
    salida = db.Column(db.Time, nullable=False)
    nocturno = db.Column(db.Boolean, default=False, nullable=False)
    pausa_minutos = db.Column(db.Integer, default=0, nullable=False)
    desde = db.Column(db.Date, nullable=False)
    hasta = db.Column(db.Date)
    estado = db.Column(db.String(20), default='vigente', nullable=False)
    observacion = db.Column(db.String(500))
    fecha_creacion = db.Column(db.DateTime, default=ahora_utc_naive, nullable=False)
    __table_args__ = (CheckConstraint('dia_semana >= 0 AND dia_semana <= 6', name='ck_horario_personal_dia'), CheckConstraint('pausa_minutos >= 0 AND pausa_minutos < 1440', name='ck_horario_personal_pausa'), CheckConstraint("estado IN ('vigente','cancelado')", name='ck_horario_personal_estado'), CheckConstraint('hasta IS NULL OR hasta >= desde', name='ck_horario_personal_fechas'))


class AusenciaPersonal(db.Model):
    """Clasificación y cómputo de la novedad laboral existente, sin repetir fechas."""
    __tablename__ = 'ausencia_personal'
    id = db.Column(db.Integer, primary_key=True)
    empleado_id = db.Column(db.Integer, db.ForeignKey('empleado_productivo.id'), nullable=False, index=True)
    novedad_id = db.Column(db.Integer, db.ForeignKey('novedad_laboral_preparatoria.id'), nullable=False, unique=True)
    tipo = db.Column(db.String(30), nullable=False)
    dias_computados = db.Column(db.Numeric(8,2), nullable=True)
    periodo = db.Column(db.String(40))
    novedad = db.relationship('NovedadLaboralPreparatoria')
    __table_args__ = (CheckConstraint("tipo IN ('vacaciones','licencia','ausencia')", name='ck_ausencia_personal_tipo'), CheckConstraint('dias_computados IS NULL OR dias_computados >= 0', name='ck_ausencia_personal_dias'))

    @property
    def desde(self): return self.novedad.fecha_desde

    @property
    def hasta(self): return self.novedad.fecha_hasta

    @property
    def detalle(self): return self.novedad.detalle

    @property
    def estado(self): return 'planificada' if self.novedad.estado == 'propuesta' else 'cancelada'

    @estado.setter
    def estado(self, estado): self.novedad.estado = 'propuesta' if estado == 'planificada' else 'cancelada'


TABLAS_PERSONAL = [PersonalDetalle.__table__, HorarioPersonal.__table__, AusenciaPersonal.__table__]
