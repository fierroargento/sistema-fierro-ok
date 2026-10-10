"""Eliminación de entidades fiscales sin uso, limitada al tenant activo."""
from sqlalchemy import select


def eliminar_entidad_fiscal_sin_uso(
    *, organizacion_id, entidad_fiscal_id, confirmacion, modelo, sesion
):
    if confirmacion != "1":
        raise ValueError("Confirmá la eliminación de la entidad fiscal.")
    try:
        entidad = sesion.query(modelo).filter(
            modelo.id == entidad_fiscal_id,
            modelo.organizacion_id == organizacion_id,
        ).with_for_update().one_or_none()
        if entidad is None:
            raise ValueError("No se encontró la entidad fiscal en el tenant activo.")
        if entidad.activa or entidad.facturacion_habilitada:
            raise ValueError("Desactivá la entidad fiscal y su facturación antes de eliminarla.")

        # Consultar las tablas directamente evita cascadas y conserva todo historial,
        # incluso vínculos desactivados y comprobantes cancelados.
        tabla_entidad = modelo.__table__
        for tabla in tabla_entidad.metadata.tables.values():
            for columna in tabla.columns:
                referencia = any(
                    fk.column is tabla_entidad.c.id for fk in columna.foreign_keys
                )
                if not referencia:
                    continue
                existe = sesion.execute(
                    select(1).select_from(tabla).where(
                        columna == entidad_fiscal_id
                    ).limit(1)
                ).first()
                if existe is not None:
                    raise ValueError(
                        "No se puede eliminar: la entidad fiscal tiene vínculos o historial. "
                        "Conservala desactivada."
                    )
        descripcion = f"{entidad.codigo} — {entidad.razon_social} (ID {entidad.id})"
        sesion.delete(entidad)
        sesion.commit()
        return f"Entidad fiscal eliminada: {descripcion}."
    except Exception:
        sesion.rollback()
        raise
