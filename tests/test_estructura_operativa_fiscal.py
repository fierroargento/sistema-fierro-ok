from pathlib import Path

from models.entidad_fiscal import EntidadFiscal
from models.sucursal_operativa import SucursalOperativa


def test_sucursal_operativa_expone_modelo_canonico():
    assert (
        SucursalOperativa.__tablename__
        == "sucursal_operativa"
    )

    columnas = {
        "id",
        "organizacion_id",
        "codigo",
        "nombre",
        "direccion",
        "localidad",
        "provincia",
        "codigo_postal",
        "es_principal",
        "activa",
        "fecha_creacion",
        "fecha_actualizacion",
        "organizacion",
    }

    assert columnas.issubset(
        set(SucursalOperativa.__dict__)
    )


def test_entidad_fiscal_expone_modelo_canonico():
    assert EntidadFiscal.__tablename__ == "entidad_fiscal"

    columnas = {
        "id",
        "organizacion_id",
        "codigo",
        "razon_social",
        "nombre_fantasia",
        "cuit",
        "condicion_iva",
        "domicilio_fiscal",
        "punto_venta_predeterminado",
        "activa",
        "facturacion_habilitada",
        "fecha_creacion",
        "fecha_actualizacion",
        "organizacion",
    }

    assert columnas.issubset(
        set(EntidadFiscal.__dict__)
    )


def test_componentes_nuevos_nacen_desactivados():
    sucursal = Path(
        "models/sucursal_operativa.py"
    ).read_text(encoding="utf-8")

    fiscal = Path(
        "models/entidad_fiscal.py"
    ).read_text(encoding="utf-8")

    assert sucursal.count("default=False") >= 2
    assert fiscal.count("default=False") >= 2

    assert "Pedido" not in sucursal
    assert "Pedido" not in fiscal
    assert "MercadoLibreCuenta" not in sucursal
    assert "MercadoLibreCuenta" not in fiscal


def test_app_registra_modelos_sin_crear_registros():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    assert (
        "from models.sucursal_operativa "
        "import SucursalOperativa"
        in app
    )
    assert (
        "from models.entidad_fiscal "
        "import EntidadFiscal"
        in app
    )

    bloque_inicio = app[
        app.index("with app.app_context():"):
    ]

    assert "SucursalOperativa(" not in bloque_inicio
    assert "EntidadFiscal(" not in bloque_inicio
