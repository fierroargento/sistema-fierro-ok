from types import SimpleNamespace

from services.migraciones_saas import (
    asegurar_codigos_unicos_por_tenant,
    especificaciones_codigos_tenant,
)


class _Preparador:
    def quote(self, identificador):
        return f'"{identificador}"'


class _Sesion:
    def __init__(self):
        self.sentencias = []
        self.commits = 0

    def execute(self, sentencia):
        self.sentencias.append(
            str(sentencia)
        )

    def commit(self):
        self.commits += 1


class _Inspector:
    def __init__(
        self,
        *,
        global_existe,
        compuesto_existe,
    ):
        self.global_existe = global_existe
        self.compuesto_existe = (
            compuesto_existe
        )

    def get_unique_constraints(self, tabla):
        restricciones = []

        if self.global_existe:
            restricciones.append({
                "name": (
                    f"uq_{tabla}_codigo_legacy"
                ),
                "column_names": [
                    "codigo",
                ],
            })

        if self.compuesto_existe:
            restricciones.append({
                "name": (
                    f"uq_{tabla}_tenant_existente"
                ),
                "column_names": [
                    "organizacion_id",
                    "codigo",
                ],
            })

        return restricciones

    def get_indexes(self, tabla):
        return []


def _db(dialecto):
    sesion = _Sesion()
    engine = SimpleNamespace(
        dialect=SimpleNamespace(
            name=dialecto,
            identifier_preparer=_Preparador(),
        ),
    )

    return (
        SimpleNamespace(
            engine=engine,
            session=sesion,
        ),
        sesion,
    )


def _inspect_fn(
    *,
    global_existe,
    compuesto_existe,
):
    def inspeccionar(engine):
        return _Inspector(
            global_existe=global_existe,
            compuesto_existe=(
                compuesto_existe
            ),
        )

    return inspeccionar


def test_postgresql_retira_global_y_crea_compuesta():
    db, sesion = _db("postgresql")

    resultados = (
        asegurar_codigos_unicos_por_tenant(
            db=db,
            inspect_fn=_inspect_fn(
                global_existe=True,
                compuesto_existe=False,
            ),
            text_fn=lambda sentencia: sentencia,
            logger_fn=None,
        )
    )

    cantidad = len(
        especificaciones_codigos_tenant()
    )
    alteraciones = [
        sentencia
        for sentencia in sesion.sentencias
        if sentencia.startswith(
            "ALTER TABLE "
        )
    ]
    creaciones = [
        sentencia
        for sentencia in sesion.sentencias
        if sentencia.startswith(
            "CREATE UNIQUE INDEX "
        )
    ]

    assert len(resultados) == cantidad
    assert len(alteraciones) == cantidad
    assert len(creaciones) == cantidad
    assert sesion.commits == cantidad * 2

    for posicion in range(
        0,
        len(sesion.sentencias),
        2,
    ):
        assert sesion.sentencias[
            posicion
        ].startswith(
            "CREATE UNIQUE INDEX "
        )
        assert sesion.sentencias[
            posicion + 1
        ].startswith(
            "ALTER TABLE "
        )

    assert all(
        resultado["global_retirado"]
        for resultado in resultados
    )
    assert all(
        not resultado["global_pendiente"]
        for resultado in resultados
    )
    assert all(
        resultado["compuesto_creado"]
        for resultado in resultados
    )

    assert all(
        'DROP CONSTRAINT "'
        in sentencia
        for sentencia in alteraciones
    )
    assert all(
        '("organizacion_id", "codigo")'
        in sentencia
        for sentencia in creaciones
    )


def test_sqlite_conserva_global_sin_reconstruir():
    db, sesion = _db("sqlite")

    resultados = (
        asegurar_codigos_unicos_por_tenant(
            db=db,
            inspect_fn=_inspect_fn(
                global_existe=True,
                compuesto_existe=False,
            ),
            text_fn=lambda sentencia: sentencia,
            logger_fn=None,
        )
    )

    cantidad = len(
        especificaciones_codigos_tenant()
    )

    assert len(resultados) == cantidad
    assert len(sesion.sentencias) == cantidad
    assert sesion.commits == cantidad

    assert not any(
        "ALTER TABLE" in sentencia
        for sentencia in sesion.sentencias
    )
    assert not any(
        "DROP CONSTRAINT" in sentencia
        for sentencia in sesion.sentencias
    )
    assert all(
        sentencia.startswith(
            "CREATE UNIQUE INDEX "
        )
        for sentencia in sesion.sentencias
    )

    assert all(
        not resultado["global_retirado"]
        for resultado in resultados
    )
    assert all(
        resultado["global_pendiente"]
        for resultado in resultados
    )
    assert all(
        resultado["compuesto_creado"]
        for resultado in resultados
    )


def test_migracion_es_idempotente_si_compuesta_existe():
    db, sesion = _db("postgresql")

    resultados = (
        asegurar_codigos_unicos_por_tenant(
            db=db,
            inspect_fn=_inspect_fn(
                global_existe=False,
                compuesto_existe=True,
            ),
            text_fn=lambda sentencia: sentencia,
            logger_fn=None,
        )
    )

    assert sesion.sentencias == []
    assert sesion.commits == 0

    assert all(
        not resultado["global_retirado"]
        for resultado in resultados
    )
    assert all(
        not resultado["global_pendiente"]
        for resultado in resultados
    )
    assert all(
        not resultado["compuesto_creado"]
        for resultado in resultados
    )
