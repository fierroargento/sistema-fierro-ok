"""Datos estructurados y control de calidad de la ficha comercial."""

import json
from decimal import Decimal


TIPOS_RELACION = {"complementario", "sustituto", "accesorio", "repuesto"}
EXTENSIONES_IMAGEN = {"jpg", "jpeg", "png", "webp"}


def cargar_json(valor, defecto):
    try:
        dato = json.loads(valor or "")
    except (TypeError, ValueError):
        return defecto
    return dato if isinstance(dato, type(defecto)) else defecto


def volcar_json(valor):
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"))


def parsear_atributos(texto):
    atributos = {}
    for numero, linea in enumerate(str(texto or "").splitlines(), 1):
        linea = linea.strip()
        if not linea:
            continue
        if "=" not in linea:
            raise ValueError(f"Atributo inválido en la línea {numero}; usá Nombre=Valor.")
        nombre, valor = (parte.strip() for parte in linea.split("=", 1))
        if not nombre or not valor:
            raise ValueError(f"Atributo incompleto en la línea {numero}.")
        atributos[nombre[:80]] = valor[:200]
    return atributos


def presentar_atributos(valor):
    return "\n".join(f"{k}={v}" for k, v in cargar_json(valor, {}).items())


def parsear_variantes(texto):
    variantes = []
    vistos = set()
    for numero, linea in enumerate(str(texto or "").splitlines(), 1):
        linea = linea.strip()
        if not linea:
            continue
        partes = [parte.strip() for parte in linea.split("|")]
        if len(partes) < 2 or not partes[0] or not partes[1]:
            raise ValueError(
                f"Variante inválida en la línea {numero}; usá SKU | Atributo=Valor."
            )
        sku = partes[0][:100]
        if sku.lower() in vistos:
            raise ValueError(f"SKU de variante repetido: {sku}.")
        vistos.add(sku.lower())
        variantes.append({"sku": sku, "opciones": partes[1][:300], "activa": True})
    return variantes


def presentar_variantes(valor):
    return "\n".join(
        f"{fila.get('sku', '')} | {fila.get('opciones', '')}"
        for fila in cargar_json(valor, [])
    )


def _lista_formulario(formulario, nombre):
    if hasattr(formulario, "getlist"):
        return formulario.getlist(nombre)
    valor = formulario.get(nombre, [])
    return valor if isinstance(valor, list) else [valor]


def parsear_atributos_estructurados(formulario):
    nombres = _lista_formulario(formulario, "atributo_nombre")
    valores = _lista_formulario(formulario, "atributo_valor")
    if not nombres and not valores:
        return parsear_atributos(formulario.get("atributos"))
    lineas = []
    for indice in range(max(len(nombres), len(valores))):
        nombre = str(nombres[indice] if indice < len(nombres) else "").strip()
        valor = str(valores[indice] if indice < len(valores) else "").strip()
        if not nombre and not valor:
            continue
        if not nombre or not valor:
            raise ValueError(f"Completá nombre y valor del atributo {indice + 1}.")
        lineas.append(f"{nombre}={valor}")
    return parsear_atributos("\n".join(lineas))


def parsear_variantes_estructuradas(formulario):
    skus = _lista_formulario(formulario, "variante_sku")
    if not skus:
        return parsear_variantes(formulario.get("variantes"))
    campos = {
        "opciones": _lista_formulario(formulario, "variante_opciones"),
        "estado": _lista_formulario(formulario, "variante_estado"),
        "peso_gr": _lista_formulario(formulario, "variante_peso_gr"),
        "largo_cm": _lista_formulario(formulario, "variante_largo_cm"),
        "ancho_cm": _lista_formulario(formulario, "variante_ancho_cm"),
        "alto_cm": _lista_formulario(formulario, "variante_alto_cm"),
        "imagen_url": _lista_formulario(formulario, "variante_imagen_url"),
    }
    variantes, vistos = [], set()
    for indice, sku_bruto in enumerate(skus):
        sku = str(sku_bruto or "").strip()[:100]
        valores = {
            clave: str(lista[indice] if indice < len(lista) else "").strip()
            for clave, lista in campos.items()
        }
        if not sku and not any(valores.values()):
            continue
        if not sku or not valores["opciones"]:
            raise ValueError(f"Completá SKU y opciones de la variante {indice + 1}.")
        if sku.lower() in vistos:
            raise ValueError(f"SKU de variante repetido: {sku}.")
        vistos.add(sku.lower())
        estado = valores["estado"] or "activa"
        if estado not in {"activa", "pausada", "discontinuada"}:
            raise ValueError(f"Estado inválido para la variante {sku}.")
        variante = {
            "sku": sku,
            "opciones": valores["opciones"][:300],
            "estado": estado,
            "activa": estado == "activa",
        }
        for campo in ("peso_gr", "largo_cm", "ancho_cm", "alto_cm"):
            texto = valores[campo].replace(",", ".")
            if texto:
                try:
                    numero = Decimal(texto)
                except Exception as exc:
                    raise ValueError(f"Medida inválida para la variante {sku}.") from exc
                if numero <= 0:
                    raise ValueError(f"Las medidas de {sku} deben ser positivas.")
                variante[campo] = str(numero.normalize())
        if valores["imagen_url"]:
            variante["imagen_url"] = valores["imagen_url"][:1000]
        variantes.append(variante)
    return variantes


def parsear_canales(formulario):
    canales = {}
    for codigo, prefijo in (("mercadolibre", "ml"), ("tiendanube", "tn")):
        identificador = str(formulario.get(f"{prefijo}_id") or "").strip()[:150]
        titulo = str(formulario.get(f"{prefijo}_titulo") or "").strip()[:255]
        descripcion = str(formulario.get(f"{prefijo}_descripcion") or "").strip()[:5000]
        habilitado = formulario.get(f"{prefijo}_habilitado") == "1"
        if identificador or titulo or descripcion or habilitado:
            canales[codigo] = {
                "habilitado": habilitado,
                "id_externo": identificador,
                "titulo": titulo,
                "descripcion": descripcion,
            }
    return canales


def validar_relaciones(ids, *, inclusion, CatalogoProducto):
    relaciones = []
    for valor in ids:
        partes = str(valor).split(":", 1)
        if len(partes) != 2 or partes[0] not in TIPOS_RELACION or not partes[1].isdigit():
            raise ValueError("La relación comercial no es válida.")
        tipo, identificador = partes[0], int(partes[1])
        destino = CatalogoProducto.query.get(identificador)
        if (
            destino is None
            or destino.id == inclusion.id
            or destino.catalogo.organizacion_id != inclusion.catalogo.organizacion_id
        ):
            raise ValueError("El producto relacionado no pertenece a la organización.")
        relaciones.append({"tipo": tipo, "catalogo_producto_id": destino.id})
    return relaciones


def subir_imagenes(archivos, *, organizacion_id, inclusion_id):
    nuevas = []
    for archivo in archivos or []:
        if not archivo or not getattr(archivo, "filename", ""):
            continue
        extension = archivo.filename.rsplit(".", 1)[-1].lower()
        if extension not in EXTENSIONES_IMAGEN:
            raise ValueError("Las imágenes deben ser JPG, PNG o WEBP.")
        contenido = archivo.read()
        if not contenido or len(contenido) > 8 * 1024 * 1024:
            raise ValueError("Cada imagen debe pesar entre 1 byte y 8 MB.")
        archivo.stream.seek(0)
        import cloudinary.uploader

        resultado = cloudinary.uploader.upload(
            archivo,
            folder=f"catalogos/{organizacion_id}/{inclusion_id}",
            resource_type="image",
            overwrite=False,
        )
        nuevas.append({
            "url": resultado.get("secure_url") or resultado.get("url"),
            "public_id": resultado.get("public_id"),
            "principal": False,
        })
    return nuevas


def calcular_completitud(inclusion, producto):
    controles = {
        "marca": inclusion.marca,
        "categoría": inclusion.categoria,
        "descripción corta": inclusion.descripcion_corta,
        "descripción pública": inclusion.descripcion_publica,
        "material": inclusion.material,
        "contenido del paquete": inclusion.contenido_paquete,
        "peso embalado": getattr(producto, "peso_gr", None),
        "largo embalado": getattr(producto, "largo_cm", None),
        "ancho embalado": getattr(producto, "ancho_cm", None),
        "alto embalado": getattr(producto, "alto_cm", None),
        "imagen": cargar_json(inclusion.imagenes_json, []),
    }
    faltantes = [nombre for nombre, valor in controles.items() if valor in (None, "", [])]
    porcentaje = round((len(controles) - len(faltantes)) * 100 / len(controles))
    return porcentaje, faltantes


def numero_visual(valor):
    if valor is None:
        return ""
    numero = Decimal(str(valor))
    return format(numero.normalize(), "f")
