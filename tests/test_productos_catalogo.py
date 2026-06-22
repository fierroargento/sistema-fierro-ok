from services.productos_catalogo import (
    bool_producto,
    normalizar_columna_producto,
    normalizar_producto_catalogo,
    peso_gr_producto,
    productos_desde_dataframe_catalogo,
    validar_producto_catalogo,
)


class DataFrameFalso:
    def __init__(self, registros):
        self._registros = registros
        self.columns = list(registros[0].keys()) if registros else []

    def to_dict(self, orient="records"):
        assert orient == "records"
        return self._registros


def test_productos_desde_dataframe_catalogo_lee_columnas_logisticas():
    df = DataFrameFalso([
        {
            "SKU": " pp6040h ",
            "Descripción": "Parrilla plegable 60x40",
            "Peso gr": "3,2 kg",
            "Alto cm": "4,5",
            "Ancho cm": 42,
            "Largo cm": 36,
            "Permite Correo": "SI",
            "Permite Vía Cargo": "no",
            "Requiere revisión logística": "x",
            "Observación logística": "Producto delicado para cotización",
        }
    ])

    productos = productos_desde_dataframe_catalogo(df)

    assert productos
    producto = productos[0]

    assert producto["sku"] == "PP6040H"
    assert producto["descripcion"] == "Parrilla plegable 60x40"
    assert producto["peso_gr"] == 3200
    assert producto["alto_cm"] == 4.5
    assert producto["ancho_cm"] == 42
    assert producto["largo_cm"] == 36
    assert producto["permite_correo"] is True
    assert producto["permite_via_cargo"] is False
    assert producto["requiere_revision_logistica"] is True
    assert producto["observacion_logistica"] == "Producto delicado para cotización"


def test_productos_desde_dataframe_catalogo_mantiene_excel_basico():
    df = DataFrameFalso([
        {
            "SKU": "KIT001",
            "Descripción": "Kit pala y atizador",
        }
    ])

    productos = productos_desde_dataframe_catalogo(df)

    assert productos
    assert productos[0]["sku"] == "KIT001"
    assert productos[0]["descripcion"] == "Kit pala y atizador"
    assert productos[0]["peso_gr"] is None
    assert productos[0]["permite_correo"] is True
    assert productos[0]["permite_via_cargo"] is True


def test_normalizar_columna_producto_soporta_acentos_y_espacios():
    assert normalizar_columna_producto("Permite Vía Cargo") == "permite_via_cargo"
    assert normalizar_columna_producto("Requiere revisión logística") == "requiere_revision_logistica"


def test_bool_producto_parsea_valores_comunes():
    assert bool_producto("SI") is True
    assert bool_producto("x") is True
    assert bool_producto("no", default=True) is False
    assert bool_producto("", default=True) is True


def test_peso_gr_producto_convierte_kg_a_gramos():
    assert peso_gr_producto("3,2 kg") == 3200
    assert peso_gr_producto("3200 gr") == 3200


def test_validar_producto_catalogo_detecta_obligatorios_y_medidas_invalidas():
    producto = normalizar_producto_catalogo({
        "sku": "",
        "descripcion": "",
        "peso_gr": "-1",
        "alto_cm": "0",
    })

    errores = validar_producto_catalogo(producto)

    assert "El SKU es obligatorio." in errores
    assert "La descripción es obligatoria." in errores
    assert "peso_gr debe ser mayor a cero." in errores
    assert "alto_cm debe ser mayor a cero." in errores
