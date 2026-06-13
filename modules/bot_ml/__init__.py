"""
modules.bot_ml
──────────────
Paquete de integración Mercado Libre del Sistema Fierro.

APB / SaaS:
- Este paquete concentra progresivamente la lógica ML que hoy vive en app.py.
- Las rutas Flask quedan en app.py.
- Las funciones migradas deben quedar cubiertas por tests del módulo destino.
- Durante la transición, app.py puede conservar wrappers delgados para no romper call sites.
"""
