"""Marca y verifica la identidad lógica de una base antes de usarla."""

import hashlib

from sqlalchemy import inspect, text


TABLA = "sistema_entorno_marcador"


def exigir_base_vacia_para_marcado(engine):
    """No permite convertir en staging una base con objetos de usuario."""
    inspector = inspect(engine)
    objetos_ajenos = []
    for esquema in inspector.get_schema_names():
        if esquema in {"pg_catalog", "information_schema"}:
            continue
        for tabla in inspector.get_table_names(schema=esquema):
            if tabla != TABLA:
                objetos_ajenos.append((esquema, tabla))
        for metodo in ("get_view_names", "get_materialized_view_names", "get_sequence_names"):
            obtener = getattr(inspector, metodo, None)
            if obtener is None:
                continue
            try:
                nombres = obtener(schema=esquema)
            except NotImplementedError:
                nombres = ()
            for nombre in nombres:
                objetos_ajenos.append((esquema, nombre))
    if engine.dialect.name == "postgresql":
        with engine.connect() as conexion:
            rutinas = conexion.execute(text(
                "SELECT routine_schema, routine_name FROM information_schema.routines "
                "WHERE routine_schema NOT IN ('pg_catalog', 'information_schema')"
            )).fetchall()
        objetos_ajenos.extend((fila[0], fila[1]) for fila in rutinas)
    if objetos_ajenos:
        muestra = ", ".join(f"{fila[0]}.{fila[1]}" for fila in objetos_ajenos[:5])
        raise RuntimeError(
            "La base no está vacía; se rechazó el marcado para proteger datos existentes"
            + (f": {muestra}." if muestra else ".")
        )
    return True


def _huella(marcador):
    valor = str(marcador or "").strip()
    if len(valor) < 32:
        raise RuntimeError("El marcador de base debe tener al menos 32 caracteres.")
    return hashlib.sha256(valor.encode()).hexdigest()


def crear_marcador_staging(engine, marcador):
    exigir_base_vacia_para_marcado(engine)
    huella = _huella(marcador)
    with engine.begin() as conexion:
        conexion.execute(text(
            f"CREATE TABLE IF NOT EXISTS {TABLA} ("
            "id INTEGER PRIMARY KEY, entorno VARCHAR(30) NOT NULL, "
            "marcador_sha256 VARCHAR(64) NOT NULL, "
            "creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        ))
        existente = conexion.execute(text(
            f"SELECT entorno, marcador_sha256 FROM {TABLA} WHERE id = 1"
        )).mappings().first()
        if existente is not None:
            if existente["entorno"] != "staging" or existente["marcador_sha256"] != huella:
                raise RuntimeError("La base ya posee un marcador diferente; operación rechazada.")
            return False
        conexion.execute(
            text(
                f"INSERT INTO {TABLA} (id, entorno, marcador_sha256) "
                "VALUES (1, :entorno, :huella)"
            ),
            {"entorno": "staging", "huella": huella},
        )
    return True


def verificar_marcador_staging(engine, marcador):
    huella = _huella(marcador)
    try:
        with engine.connect() as conexion:
            fila = conexion.execute(text(
                f"SELECT entorno, marcador_sha256 FROM {TABLA} WHERE id = 1"
            )).mappings().first()
    except Exception as error:
        raise RuntimeError(
            "La base no está preparada como staging o no puede verificarse."
        ) from error
    if fila is None or fila["entorno"] != "staging" or fila["marcador_sha256"] != huella:
        raise RuntimeError("El marcador de la base no coincide con esta instalación de staging.")
    return True


def verificar_marcador_aplicacion(app, db, marcador):
    """Mantiene el manejo del contexto fuera del módulo principal."""
    with app.app_context():
        return verificar_marcador_staging(db.engine, marcador)
