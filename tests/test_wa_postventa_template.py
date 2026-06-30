from types import SimpleNamespace

from services.wa_postventa_template import template_postventa_para_pedido


def test_template_postventa_parrilla_para_sku_pp6040():
    pedido = SimpleNamespace(
        producto="Parrilla Camping Plegable Portatil 60 X 40 Rebatible",
        sku="PP6040H",
        items=[],
    )

    assert template_postventa_para_pedido(pedido) == "postventa_parrilla"


def test_template_postventa_parrilla_para_sku_brasero():
    pedido = SimpleNamespace(
        producto="Brasero Cuna Leñero Canasta De Hierro P/ Parrilla Grande",
        sku="B5030H",
        items=[],
    )

    assert template_postventa_para_pedido(pedido) == "postventa_parrilla"


def test_template_postventa_parrilla_para_combo_sku():
    pedido = SimpleNamespace(
        producto="Combo Parrilla 100x60 + Atizador + Pala + Brasero Reforzado",
        sku="PA10060+B40+KITPACH",
        items=[],
    )

    assert template_postventa_para_pedido(pedido) == "postventa_parrilla"


def test_template_postventa_generica_para_sku_cuadros_mdf():
    pedido = SimpleNamespace(
        producto="Cuadro Calado Gatitos MDF FibroPlus Negro 3mm 43x30 cm",
        sku="C-MDF-156",
        items=[
            SimpleNamespace(
                sku="C-MDF-162",
                descripcion="Cuadro Calado MDF FibroPlus Negro 3mm Flores Triptico",
            )
        ],
    )

    assert template_postventa_para_pedido(pedido) == "postventa_generica"


def test_template_postventa_generica_para_sku_reloj_mdf():
    pedido = SimpleNamespace(
        producto="Reloj De Pared Deco Homero Simpson En Madera Mdf Negro",
        sku="R-MDF-006",
        items=[],
    )

    assert template_postventa_para_pedido(pedido) == "postventa_generica"


def test_template_postventa_generica_no_confunde_palabra_home_con_pala():
    pedido = SimpleNamespace(
        producto="Cuadro Decorativo Living Palabra Home Enlazada Madera Mdf Negro",
        sku="C-MDF-124",
        items=[],
    )

    assert template_postventa_para_pedido(pedido) == "postventa_generica"


def test_template_postventa_parrilla_fallback_si_no_hay_sku():
    pedido = SimpleNamespace(
        producto="Parrilla de hierro reforzada",
        sku="",
        items=[],
    )

    assert template_postventa_para_pedido(pedido) == "postventa_parrilla"
