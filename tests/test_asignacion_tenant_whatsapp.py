from pathlib import Path


def test_flujo_exige_tres_estados_y_confirmacion():
    texto = Path("services/asignacion_tenant_whatsapp.py").read_text(encoding="utf-8")
    assert 'estado="preparada"' in texto
    assert 'propuesta.estado = "aprobada"' in texto
    assert 'propuesta.estado = "aplicada"' in texto
    assert '!= "ASIGNAR"' in texto


def test_preparacion_solo_usa_pedidos_del_tenant():
    texto = Path("services/asignacion_tenant_whatsapp.py").read_text(encoding="utf-8")
    assert "Pedido.query.filter_by(organizacion_id=int(organizacion_id))" in texto
    assert "Candidato único por pedido ya aislado." in texto


def test_aplicacion_revalida_antes_de_escribir():
    texto = Path("services/asignacion_tenant_whatsapp.py").read_text(encoding="utf-8")
    inicio = texto.index("def aplicar_propuesta_whatsapp(")
    bloque = texto[inicio:]
    assert bloque.index("_revalidar(") < bloque.index("mensaje.organizacion_id =")
    assert "mensaje.unidad_negocio_id = propuesta.unidad_negocio_id" in bloque


def test_servicio_no_contiene_transporte_externo():
    texto = Path("services/asignacion_tenant_whatsapp.py").read_text(encoding="utf-8").lower()
    for prohibido in ("requests", "oauth", "access_token", "webhook", "graph.facebook"):
        assert prohibido not in texto
