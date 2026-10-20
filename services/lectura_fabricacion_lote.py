"""Lecturas compartidas únicamente durante una fase de un lote de fabricación.

Sin estado global, sin cambios de permisos y sin reutilizar datos entre peticiones.
El alta manual y los movimientos operativos conservan su recorrido habitual.
"""


class LecturaFabricacion:
    def __init__(self, session, organizacion_id):
        self.session = session
        self.organizacion_id = organizacion_id
        self.recursos = {}
        self.esquemas = {}
        self.habilitaciones = {}

    def comprobar(self, session, organizacion_id):
        if self.session is not session or self.organizacion_id != organizacion_id:
            raise ValueError('La lectura del lote no pertenece a esta sesión y organización.')
        if session.new or session.dirty or session.deleted:
            raise ValueError('La lectura del lote requiere una fase sin escrituras pendientes.')

    def esquema(self, funcion):
        if funcion not in self.esquemas:
            self.esquemas[funcion] = funcion(self.session)
        return self.esquemas[funcion]

    def recurso(self, Modelo, ident):
        clave = (Modelo, ident)
        if clave not in self.recursos:
            self.recursos[clave] = self.session.query(Modelo).filter_by(
                id=ident, organizacion_id=self.organizacion_id).populate_existing().first()
        return self.recursos[clave]

    def exigir_insumo(self, insumo, unidad):
        from services.producto_habilitaciones import exigir_uso_insumo
        clave = (insumo.id, unidad)
        if clave not in self.habilitaciones:
            try:
                exigir_uso_insumo(insumo, 'insumo', self.session, unidad)
                self.habilitaciones[clave] = None
            except ValueError as error:
                self.habilitaciones[clave] = str(error)
        if self.habilitaciones[clave] is not None:
            raise ValueError(self.habilitaciones[clave])
