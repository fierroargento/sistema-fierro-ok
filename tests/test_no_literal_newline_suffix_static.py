from pathlib import Path


def test_no_hay_saltos_n_literal_al_final_de_linea_en_python():
    ignorar_partes = {
        "venv",
        ".venv",
        "__pycache__",
        ".git",
        ".pytest_cache",
    }

    problemas = []

    for path in Path(".").rglob("*.py"):
        partes = set(path.parts)

        if partes & ignorar_partes:
            continue

        texto = path.read_text(encoding="utf-8", errors="replace")

        for nro, linea in enumerate(texto.splitlines(), 1):
            if linea.rstrip().endswith("\\n"):
                problemas.append(f"{path}:{nro}: {linea}")

    assert not problemas, "Lineas con \\\\n literal al final:\\n" + "\\n".join(problemas)
