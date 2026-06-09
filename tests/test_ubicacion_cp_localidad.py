from services import ubicacion_cp


class PedidoFake:
    def __init__(self, localidad="", provincia="", codigo_postal="", direccion=""):
        self.localidad = localidad
        self.provincia = provincia
        self.codigo_postal = codigo_postal
        self.direccion = direccion
        self.cpa = ""
        self.ubicacion_fuente = ""
        self.ubicacion_confianza = ""
        self.latitud_cliente = None
        self.longitud_cliente = None


def test_resolver_cp_por_localidad_provincia_desde_base_local(monkeypatch):
    data = [
        {
            "cp": "5300",
            "localidad": "La Rioja",
            "provincia": "La Rioja",
        }
    ]

    def fake_cargar(path):
        if "codigos_postales_ar.json" in path:
            return data
        return None

    monkeypatch.setattr(ubicacion_cp, "_cargar_json_seguro", fake_cargar)

    resultado = ubicacion_cp.resolver_cp_por_localidad_provincia(
        localidad="La Rioja Capital",
        provincia="La Rioja",
    )

    assert resultado["codigo_postal"] == "5300"
    assert resultado["localidad"] == "La Rioja"
    assert resultado["provincia"] == "La Rioja"


def test_resolver_cp_por_localidad_provincia_no_inventa_si_hay_ambiguedad(monkeypatch):
    data = [
        {
            "cp": "1650",
            "localidad": "San Martin",
            "provincia": "Buenos Aires",
        },
        {
            "cp": "5570",
            "localidad": "San Martin",
            "provincia": "Mendoza",
        },
    ]

    def fake_cargar(path):
        if "codigos_postales_ar.json" in path:
            return data
        return None

    monkeypatch.setattr(ubicacion_cp, "_cargar_json_seguro", fake_cargar)

    resultado = ubicacion_cp.resolver_cp_por_localidad_provincia(
        localidad="San Martin",
        provincia="",
    )

    assert resultado is None


def test_normalizar_ubicacion_pedido_completa_cp_por_localidad(monkeypatch):
    def fake_resolver(localidad, provincia=""):
        assert localidad == "La Rioja Capital"
        assert provincia == "La Rioja"
        return {
            "codigo_postal": "5300",
            "localidad": "La Rioja",
            "provincia": "La Rioja",
            "fuente": "test",
            "confianza": "media",
        }

    monkeypatch.setattr(
        ubicacion_cp,
        "resolver_cp_por_localidad_provincia",
        fake_resolver,
    )

    pedido = PedidoFake(
        localidad="La Rioja Capital",
        provincia="La Rioja",
        codigo_postal="",
    )

    resultado = ubicacion_cp.normalizar_ubicacion_pedido(pedido)

    assert pedido.codigo_postal == "5300"
    assert "codigo_postal" in resultado["completados"]
