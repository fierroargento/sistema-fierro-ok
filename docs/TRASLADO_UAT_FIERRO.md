# Traslado de fabricación real a Fierro — staging

Estado: preparado; no ejecutado en la base remota. Ensayo UAT no se borra ni se desactiva en este paso.

## 1. Simular

Después de desplegar integración en staging:

```bash
python -m scripts.trasladar_uat_fierro --staging --origen 3 --destino 1
```

No escribe. Informa cantidades, dependencias fuera de Fierro y opciones reales disponibles. La lista explícita revisada contiene 33 códigos de insumos y 384 SKU. No selecciona nuevos artículos por descarte ni copia los registros sintéticos.

El resultado muestra también el ID de Codimat entre `disponibles.proveedores_codimat`. Elegirlo explícitamente con `--proveedor-codimat ID` en las siguientes simulaciones. No se crea un proveedor ni se relacionan materiales por similitud de descripción.

## 2. Resolver los recursos pendientes

La salida separa las dependencias por línea de producto y muestra los recursos activos de Fierro. Si falta una máquina o un área real, primero completarla en los módulos existentes, con sus datos/costos reales. No convertir recursos sintéticos en reales cambiando sólo su nombre ni asignarles costos inventados.

El archivo JSON de equivalencias permite este formato (los IDs son exclusivamente ejemplos):

```json
{
  "por_linea": {
    "Herrería": {"empleado_productivo": {"1": 10}},
    "Láser": {"empleado_productivo": {"1": 11}, "maquina_productiva": {"1": 12}}
  }
}
```

Usar exactamente los nombres de línea e IDs del diagnóstico. La clave izquierda identifica el recurso anterior; el valor identifica el recurso real de Fierro. Un mapa global, por ejemplo `"maquina_productiva":{"1":12}`, sólo corresponde si ese reemplazo aplica a todas las líneas que utilizan la máquina anterior.

Repetir la simulación con `--mapa /tmp/mapa_traslado.json --proveedor-codimat ID`. No vuelve a importar archivos ni crea identidades. Antes de aplicar, revisar que `bloqueos` esté vacío y que los reemplazos sean los correctos. El programa bloquea cualquier traslado si faltan identidades, un recurso sigue siendo ajeno/sintético, un combo cruza perfiles no trasladados o hay perfiles/versiones incompatibles en destino.

## 3. Ejecutar cuando el plan esté completo

Antes de escribir, verificar en Render que staging y producción estén asociados a recursos de base diferentes. El nombre de base por sí solo no acredita esa separación. Sólo entonces puede usarse `--bases-separadas-verificadas`.

Al comando de simulación completo y ya revisado se agregan `--aplicar --bases-separadas-verificadas`. No ejecutar en producción. El CLI exige laboratorio desconectado, rama de integración, URL de servicio staging y, en PostgreSQL, base `sistema_fierro_staging`.

Una sola transacción conserva IDs de insumos, productos, perfiles, piezas, cantidades, tiempos y versiones históricas. Reasigna sólo los recursos expresamente elegidos; si cambia la mano de obra, actualiza tarifa del despiece y su huella junto con la composición. Las versiones de costo se conservan preparatorias, sin recalcularlas ni activarlas. No modifica precios de proveedores, stock, cajas, pagos ni conexiones externas.

Los trece códigos Codimat se vinculan a los materiales existentes de Fierro. El código de proveedor 3951 corresponde al material interno 1985, según confirmación del usuario: conserva esa identidad y sus consumos. Si ya había un vínculo 1985 del mismo material/proveedor, se actualiza ese vínculo a 3951 conservando su ID e historial. Los conflictos se bloquean.

## 4. Verificar y retirar UAT

Comprobar que los materiales se ven en Fierro, revisar una ficha de cada línea y un combo, cargar la lista Codimat y revisar las fuentes de mano de obra/máquina con sus valores reales. Los costos históricos preparatorios no representan por sí solos un costo nuevo validado con las fuentes actuales.

El retiro final de Ensayo UAT queda pendiente de revisar las referencias restantes: conserva datos de prueba e históricos de importación, sin trasladarlos como datos reales. No se borra ninguna unidad ni registro en este programa. La asignación general de todo el catálogo global de productos a una unidad sigue siendo un bloque distinto del traslado de sus perfiles de costeo.
