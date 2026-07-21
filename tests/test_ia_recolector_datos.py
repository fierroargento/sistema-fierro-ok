from services.ia_recolector_datos import (
    capitalizar_texto_fierro,
    ia_campo_vacio,
    ia_cp_valido,
    ia_dni_valido,
    ia_texto_menciona_autorizado,
    normalizar_datos_ia_fierro,
    normalizar_direccion_fierro,
)


def test_capitaliza_nombres_y_conectores():
    assert (
        capitalizar_texto_fierro(
            "  juan   de la cruz  "
        )
        == "Juan de la Cruz"
    )


def test_normaliza_direccion_y_abreviaturas():
    assert (
        normalizar_direccion_fierro(
            "avenida mitre nro 500"
        )
        == "Av. Mitre N° 500"
    )


def test_valida_dni_y_cp():
    assert ia_dni_valido("30.111.222") == "30111222"
    assert ia_dni_valido("123") == ""
    assert ia_cp_valido("8500") == "8500"


def test_detecta_datos_de_autorizado():
    assert ia_texto_menciona_autorizado(
        "Quien recibe es Juan"
    ) is True
    assert ia_texto_menciona_autorizado(
        "Mi DNI es 30111222"
    ) is False


def test_campo_vacio():
    assert ia_campo_vacio("   ") is True
    assert ia_campo_vacio("dato") is False


def test_normaliza_diccionario_detectado():
    datos = normalizar_datos_ia_fierro({
        "nombre": "juan",
        "apellido": "perez",
        "direccion": "av mitre nro 500",
        "dni": "30.111.222",
        "codigo_postal": "a8500abc",
    })

    assert datos["nombre"] == "Juan"
    assert datos["apellido"] == "Perez"
    assert datos["direccion"] == "Av. Mitre N° 500"
    assert datos["dni"] == "30111222"
    assert datos["codigo_postal"] == "A8500ABC"


def test_servicio_no_depende_de_app():
    from pathlib import Path

    texto = Path(
        "services/ia_recolector_datos.py"
    ).read_text(encoding="utf-8")

    assert "from app import" not in texto
    assert "import app" not in texto
    assert "db.session" not in texto


def test_parser_clasico_detecta_cp_simple():
    from services.ia_recolector_datos import (
        ia_extraer_datos_clasico_fierro,
    )

    assert ia_extraer_datos_clasico_fierro(
        "1617",
        {},
    )["codigo_postal"] == "1617"


def test_parser_clasico_detecta_dni_etiquetado():
    from services.ia_recolector_datos import (
        ia_extraer_datos_clasico_fierro,
    )

    assert ia_extraer_datos_clasico_fierro(
        "Mi DNI es 30.111.222",
        {},
    )["dni"] == "30111222"


def test_parser_clasico_no_pisa_datos_previos():
    from services.ia_recolector_datos import (
        ia_extraer_datos_clasico_fierro,
    )

    datos = ia_extraer_datos_clasico_fierro(
        "DNI 30.111.222 CP 8500",
        {
            "dni": "40111222",
            "codigo_postal": "9000",
        },
    )

    assert "dni" not in datos
    assert "codigo_postal" not in datos


def test_parser_clasico_esta_fuera_de_app():
    from pathlib import Path

    app = Path("app.py").read_text(encoding="utf-8")
    servicio = Path(
        "services/ia_recolector_datos.py"
    ).read_text(encoding="utf-8")

    assert (
        "def ia_extraer_datos_clasico_fierro("
        not in app
    )
    assert (
        "def ia_extraer_datos_clasico_fierro("
        in servicio
    )
    assert "normalizar_telefono_service(" in servicio
