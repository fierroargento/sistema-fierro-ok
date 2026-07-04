"""
services/pedidos_acciones.py

Reglas puras para decidir acciones operativas de pedidos.

APB modular:
- Este módulo no usa Flask.
- No arma URLs.
- No renderiza botones.
- Solo decide reglas de negocio.
"""

def _normalizar_ascii_accion(valor):
    import unicodedata

    texto = str(valor or "").strip().lower()

    try:
        texto = texto.encode("latin1").decode("utf-8")
    except Exception:
        pass

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto


def _es_ml_acordas(pedido):
    canal = _normalizar_ascii_accion(getattr(pedido, "canal", "") or "")
    ml_tipo = _normalizar_ascii_accion(getattr(pedido, "ml_tipo", "") or "")

    return (
        canal == "mercado libre"
        and "acordas" in ml_tipo
        and "entrega" in ml_tipo
    )
def _es_correo_o_andreani(pedido):
    empresa = str(getattr(pedido, "empresa_envio", "") or "").strip()
    return empresa in ["Andreani", "Correo Argentino"]


def necesita_completar_carga_etiqueta_o_seguimiento(pedido):
    """
    ML Acordas con Correo/Andreani necesita Completar carga cuando falta
    etiqueta o seguimiento. No debe quedar en Generar etiqueta porque el
    operador necesita cargar ambos datos operativos.
    """
    if not pedido:
        return False

    if str(getattr(pedido, "estado", "") or "") != "Cargando Pedido":
        return False

    if not _es_ml_acordas(pedido):
        return False

    if not _es_correo_o_andreani(pedido):
        return False

    return bool(
        not str(getattr(pedido, "etiqueta_archivo", "") or "").strip()
        or not str(getattr(pedido, "seguimiento", "") or "").strip()
    )


def debe_mostrar_accion_completar_carga(
    pedido,
    necesita_completar_carga_tn=False,
    requiere_contacto=False,
    estados_post_despacho=None,
    estados_despacho_operativo=None,
):
    """
    Decide si la acción principal debe ser "Completar carga".

    Reglas actuales migradas desde app.py:
    - Tienda Nube con carga incompleta debe volver a completar carga.
    - Si falta contacto/datos operativos y el pedido no está en estados posteriores,
      también debe completar carga.
    """
    if not pedido:
        return False

    if necesita_completar_carga_tn:
        return True

    if necesita_completar_carga_etiqueta_o_seguimiento(pedido):
        return True

    estados_post_despacho = estados_post_despacho or []
    estados_despacho_operativo = estados_despacho_operativo or []

    estados_excluidos = list(estados_post_despacho) + list(estados_despacho_operativo) + [
        "Entregado",
        "Finalizado",
    ]

    return bool(
        requiere_contacto
        and getattr(pedido, "estado", None) not in estados_excluidos
    )
