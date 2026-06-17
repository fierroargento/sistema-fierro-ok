import json

from modules.whatsapp import cross_sell


def _guardar_catalogo(path, sku="KPADES", imagen_url=""):
    data = {
        "productos": {
            sku: {
                "nombre": "Kit prueba",
                "descripcion": "Descripción prueba",
                "precio": 8500,
                "imagen_url": imagen_url,
            }
        }
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def test_obtener_producto_respeta_imagen_url_publica_del_catalogo(tmp_path, monkeypatch):
    catalogo_path = tmp_path / "catalogo_config.json"
    productos_dir = tmp_path / "productos"
    productos_dir.mkdir()

    url_publica = "https://res.cloudinary.com/demo/image/upload/test/wa.jpg"
    _guardar_catalogo(catalogo_path, imagen_url=url_publica)

    monkeypatch.setattr(cross_sell, "CATALOGO_PATH", catalogo_path)
    monkeypatch.setattr(cross_sell, "PRODUCTOS_DIR", productos_dir)

    producto = cross_sell.obtener_producto("KPADES")

    assert producto["imagen_url"] == url_publica


def test_obtener_producto_usa_fallback_local_si_no_hay_url_publica(tmp_path, monkeypatch):
    catalogo_path = tmp_path / "catalogo_config.json"
    productos_dir = tmp_path / "productos"
    ruta_producto = productos_dir / "KPADES"
    ruta_producto.mkdir(parents=True)
    (ruta_producto / "wa.jpg").write_text("fake image", encoding="utf-8")

    _guardar_catalogo(catalogo_path, imagen_url="")

    monkeypatch.setattr(cross_sell, "CATALOGO_PATH", catalogo_path)
    monkeypatch.setattr(cross_sell, "PRODUCTOS_DIR", productos_dir)

    producto = cross_sell.obtener_producto("KPADES")

    assert producto["imagen_url"] == "/static/catalogo/productos/KPADES/wa.jpg"


def test_obtener_producto_deja_imagen_vacia_si_no_hay_url_ni_archivo(tmp_path, monkeypatch):
    catalogo_path = tmp_path / "catalogo_config.json"
    productos_dir = tmp_path / "productos"
    productos_dir.mkdir()

    _guardar_catalogo(catalogo_path, imagen_url="")

    monkeypatch.setattr(cross_sell, "CATALOGO_PATH", catalogo_path)
    monkeypatch.setattr(cross_sell, "PRODUCTOS_DIR", productos_dir)

    producto = cross_sell.obtener_producto("KPADES")

    assert producto["imagen_url"] == ""
