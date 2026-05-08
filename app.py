# fix_preparacion.py
# Aplica corrección APB:
# - agrega menú "Pedidos en preparación" para admin/carga
# - agrega ruta /pedidos-preparacion
# - saca "Etiqueta Lista" del Inicio de carga
# - reutiliza index.html con título/subtítulo de preparación

from pathlib import Path
import re

ROOT = Path(".")
APP = ROOT / "app.py"
BASE = ROOT / "templates" / "base.html"
INDEX = ROOT / "templates" / "index.html"

for p in [APP, BASE, INDEX]:
    if not p.exists():
        raise SystemExit(f"No encontré {p}. Ejecutá este script desde la raíz del repo.")

app = APP.read_text(encoding="utf-8")
base = BASE.read_text(encoding="utf-8")
index = INDEX.read_text(encoding="utf-8")

# 1) Reemplazar estados_visibles_inicio y agregar helpers preparación
nuevo_estados = '''def estados_visibles_inicio():
    rol = rol_actual()

    if rol == "admin":
        return [
            "Cargando Pedido",
            "Etiqueta Lista",
            "Etiqueta Impresa",
            "Embalado",
            "Despachado",
            "Con demora de entrega",
            "Con reclamo en transporte",
            "Verificar llegada a destino",
            "Listo para retirar",
            "No entregado",
            "Reclamar a Mercado Libre",
            "Entregado",
        ]

    if rol == "carga":
        # APB: Carga no debe mezclar pedidos de preparación/despacho en Inicio.
        # "Etiqueta Lista", "Etiqueta Impresa" y "Embalado" se trabajan desde Pedidos en preparación.
        return [
            "Cargando Pedido",
            "Despachado",
            "Con demora de entrega",
            "Con reclamo en transporte",
            "Verificar llegada a destino",
            "Listo para retirar",
            "No entregado",
            "Reclamar a Mercado Libre",
            "Entregado",
        ]

    if rol == "despacho":
        return ["Etiqueta Lista", "Etiqueta Impresa", "Embalado"]

    return []


def puede_ver_pedidos_preparacion():
    return rol_actual() in ["admin", "carga"]


def estados_visibles_preparacion():
    if not puede_ver_pedidos_preparacion():
        return []
    return ["Etiqueta Lista", "Etiqueta Impresa", "Embalado"]
'''

app2, n = re.subn(
    r'def estados_visibles_inicio\(\):.*?(?=\n\ndef titulo_inicio_por_rol\(\):)',
    nuevo_estados.rstrip(),
    app,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit("No pude reemplazar def estados_visibles_inicio(). Revisá app.py.")
app = app2

# 2) Insertar ruta /pedidos-preparacion antes de despacho_mobile
if 'def pedidos_preparacion()' not in app:
    ruta_preparacion = r'''

@app.route("/pedidos-preparacion")
@login_required
def pedidos_preparacion():
    if not puede_ver_pedidos_preparacion():
        return redirect(url_for("inicio"))

    pedidos = Pedido.query.all()

    cambios = False
    for pedido in pedidos:
        telefono_original = pedido.telefono or ""
        telefono_normalizado = normalizar_telefono(telefono_original)
        if telefono_original and telefono_normalizado and telefono_original != telefono_normalizado:
            pedido.telefono = telefono_normalizado
            cambios = True

        estado_anterior = pedido.estado
        actualizar_estado_automatico(pedido)
        if pedido.estado != estado_anterior:
            cambios = True

    if cambios:
        db.session.commit()

    estados = estados_visibles_preparacion()
    pedidos = [p for p in pedidos if p.estado in estados]
    pedidos.sort(key=orden_inicio_pedido)

    return render_template(
        "index.html",
        pedidos=pedidos,
        resumen_operativo=resumen_operativo(pedidos),
        accion_sugerida_pedido=accion_sugerida_pedido,
        texto_boton_estado=texto_boton_estado,
        puede_imprimir_etiqueta_directamente=puede_imprimir_etiqueta_directamente,
        ok_feedback=(request.args.get("ok") or "").strip(),
        titulo_pagina="Pedidos en preparación",
        subtitulo_pagina="Pedidos ya cargados que esperan impresión, embalado o despacho.",
        modo_preparacion=True,
    )
'''
    marcador = '\n\n@app.route("/despacho-mobile")'
    if marcador not in app:
        raise SystemExit("No encontré el lugar para insertar /pedidos-preparacion.")
    app = app.replace(marcador, ruta_preparacion + marcador, 1)

# 3) Ajustar heading de index para aceptar título/subtítulo override
index = index.replace(
    '<h2>{{ titulo_inicio_por_rol() }}</h2>\n            <p class="listado-sub">{{ subtitulo_inicio_por_rol() }}</p>',
    '<h2>{{ titulo_pagina or titulo_inicio_por_rol() }}</h2>\n            <p class="listado-sub">{{ subtitulo_pagina or subtitulo_inicio_por_rol() }}</p>',
)

# 4) Agregar link al menú lateral
if 'pedidos_preparacion' not in base:
    bloque_historico = '''            {% if puede_ver_historico() %}
            <a href="{{ url_for('historico') }}">Histórico</a>
            {% endif %}'''
    bloque_nuevo = '''            {% if puede_ver_historico() %}
            <a href="{{ url_for('historico') }}">Histórico</a>
            {% endif %}
            {% if rol_actual in ["admin", "carga"] %}
            <a href="{{ url_for('pedidos_preparacion') }}">Pedidos en preparación</a>
            {% endif %}'''
    if bloque_historico not in base:
        raise SystemExit("No encontré el bloque Histórico en templates/base.html.")
    base = base.replace(bloque_historico, bloque_nuevo, 1)

APP.write_text(app, encoding="utf-8", newline="\n")
BASE.write_text(base, encoding="utf-8", newline="\n")
INDEX.write_text(index, encoding="utf-8", newline="\n")

print("OK: aplicado fix Pedidos en preparación.")
print("Archivos modificados: app.py, templates/base.html, templates/index.html")
