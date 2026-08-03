from pathlib import Path

from services.migraciones_saas import (
    especificaciones_codigos_tenant,
)


RAIZ = Path(__file__).resolve().parents[1]


def _leer(ruta):
    return (
        RAIZ
        .joinpath(ruta)
        .read_text(encoding="utf-8")
    )


MODELOS_CODIGO_TENANT = (
    (
        "models/catalogo.py",
        "uq_catalogo_organizacion_codigo",
    ),
    (
        "models/cliente_crm.py",
        "uq_cliente_crm_organizacion_codigo",
    ),
    (
        "models/etapa_crm.py",
        "uq_etapa_crm_organizacion_codigo",
    ),
    (
        "models/unidad_negocio.py",
        "uq_unidad_negocio_organizacion_codigo",
    ),
    (
        "models/sucursal_operativa.py",
        "uq_sucursal_operativa_organizacion_codigo",
    ),
    (
        "models/entidad_fiscal.py",
        "uq_entidad_fiscal_organizacion_codigo",
    ),
    (
        "models/modulo_organizacion.py",
        "uq_modulo_organizacion_codigo",
    ),
)


def _bloque_codigo(contenido):
    inicio = contenido.index(
        "    codigo = db.Column("
    )
    fin = contenido.index(
        "\n    )",
        inicio,
    )

    return contenido[inicio:fin]


def test_modelos_declaran_unicidad_compuesta():
    for archivo, nombre in (
        MODELOS_CODIGO_TENANT
    ):
        contenido = _leer(archivo)

        assert "UniqueConstraint(" in contenido
        assert '"organizacion_id"' in contenido
        assert '"codigo"' in contenido
        assert f'name="{nombre}"' in contenido
        assert (
            "unique=True"
            not in _bloque_codigo(contenido)
        )


def test_especificaciones_coinciden_con_modelos():
    esperadas = {
        nombre
        for _archivo, nombre in (
            MODELOS_CODIGO_TENANT
        )
    }
    reales = {
        nombre
        for _tabla, nombre in (
            especificaciones_codigos_tenant()
        )
    }

    assert reales == esperadas


def test_cuit_permanece_globalmente_unico():
    contenido = _leer(
        "models/entidad_fiscal.py"
    )
    inicio = contenido.index(
        "    cuit = db.Column("
    )
    fin = contenido.index(
        "\n    )",
        inicio,
    )

    assert (
        "unique=True"
        in contenido[inicio:fin]
    )


def test_cuentas_externas_permanecen_unicas():
    contenido = _leer(
        "models/vinculo_canal_comercial.py"
    )

    assert contenido.count(
        "unique=True"
    ) == 2


def test_configuracion_sigue_unica_por_entidad():
    contenido = _leer(
        "models/configuracion_fiscal.py"
    )

    assert "entidad_fiscal_id = db.Column(" in contenido
    assert contenido.count(
        "unique=True"
    ) == 1


def test_servicios_validan_codigo_por_tenant():
    estructura = _leer(
        "services/estructura_admin.py"
    )
    bootstrap = _leer(
        "services/estructura_empresarial.py"
    )
    crm = _leer(
        "services/crm_admin.py"
    )

    assert (
        ".filter_by(codigo=codigo)"
        not in estructura
    )
    assert (
        ".filter_by(codigo=codigo)"
        not in bootstrap
    )
    assert (
        ".filter_by(codigo=codigo)"
        not in crm
    )


def test_migracion_no_reconstruye_tablas():
    contenido = _leer(
        "services/migraciones_saas.py"
    )

    assert "DROP TABLE" not in contenido
    assert "ALTER TABLE {tabla_sql} " in contenido
    assert "DROP CONSTRAINT" in contenido
    assert (
        "CREATE UNIQUE INDEX IF NOT EXISTS"
        in contenido
    )


def test_sqlite_legacy_se_conserva_seguro():
    contenido = _leer(
        "services/migraciones_saas.py"
    )

    assert 'dialecto == "postgresql"' in contenido
    assert "global_pendiente = True" in contenido
    assert "RENAME TO" not in contenido


def test_bootstrap_ejecuta_unicidad_tenant():
    contenido = _leer("app.py")

    assert (
        "asegurar_codigos_unicos_por_tenant("
        in contenido
    )
