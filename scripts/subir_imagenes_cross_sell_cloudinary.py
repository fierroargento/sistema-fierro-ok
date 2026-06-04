import os
from pathlib import Path

import cloudinary
import cloudinary.uploader


SKUS_CROSS_SELL = [
    "KPADES",
    "BPPC01",
    "KITPACH",
    "B4030H",
    "B5030H",
]


def main():
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    api_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
    api_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()

    if not cloud_name or not api_key or not api_secret:
        raise RuntimeError(
            "Faltan variables Cloudinary. Configurá CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY y CLOUDINARY_API_SECRET antes de ejecutar."
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )

    base_dir = Path(__file__).resolve().parent.parent
    productos_dir = base_dir / "static" / "catalogo" / "productos"

    print("")
    print("Subiendo imágenes cross-sell a Cloudinary...")
    print("")

    urls = {}

    for sku in SKUS_CROSS_SELL:
        ruta_imagen = productos_dir / sku / "wa.jpg"

        if not ruta_imagen.exists():
            print(f"[FALTA] {sku}: no existe {ruta_imagen}")
            continue

        public_id = f"sistema_fierro/cross_sell/{sku}/wa"

        try:
            resultado = cloudinary.uploader.upload(
                str(ruta_imagen),
                public_id=public_id,
                overwrite=True,
                resource_type="image",
            )

            secure_url = resultado.get("secure_url", "")

            if not secure_url:
                print(f"[ERROR] {sku}: Cloudinary no devolvió secure_url")
                continue

            urls[sku] = secure_url
            print(f"[OK] {sku}")
            print(secure_url)
            print("")

        except Exception as e:
            print(f"[ERROR] {sku}: {e}")

    print("")
    print("RESUMEN PARA PEGAR EN catalogo_config.json")
    print("------------------------------------------------")
    for sku, url in urls.items():
        print(f'{sku}: "imagen_url": "{url}"')


if __name__ == "__main__":
    main()