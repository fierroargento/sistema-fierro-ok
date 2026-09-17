# Configuración segura de entornos

Sistema Fierro arranca en modo `desarrollo` y desconectado. La presencia de
tokens de Mercado Libre, Tienda Nube, WhatsApp o Cloudinary no habilita por sí
sola ninguna salida real.

```text
SISTEMA_FIERRO_ENTORNO=desarrollo
CONEXIONES_EXTERNAS_HABILITADAS=false
EFECTOS_EXTERNOS_HABILITADOS=false
WEBHOOKS_HABILITADOS=false
SCHEDULER_ENABLED=false
BOOTSTRAP_BASE_DATOS_HABILITADO=false
IA_AUTO_RESPUESTA=0
```

Las consultas y descargas también están bloqueadas. Para abrir red en un
entorno futuro hacen falta simultáneamente la llave maestra
`CONEXIONES_EXTERNAS_HABILITADAS=true` y la llave específica del canal, por
ejemplo `ML_CONEXION_HABILITADA=true`. Tener credenciales cargadas nunca basta.

Cada canal exige además su propia llave: `ML_EFECTOS_HABILITADOS`,
`TN_EFECTOS_HABILITADOS`, `WHATSAPP_EFECTOS_HABILITADOS` o
`CLOUDINARY_EFECTOS_HABILITADOS`. Los webhooks requieren
`ML_WEBHOOK_HABILITADO` o `TN_WEBHOOK_HABILITADO` junto con la llave maestra.

No habilitar estas variables para reemplazar DUX. La conexión se realizará por
canal, con un procedimiento posterior de certificación, comparación y rollback.
