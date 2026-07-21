"""
Extensiones compartidas de la aplicación.

Las extensiones se crean sin una instancia Flask concreta para evitar
que los módulos operativos dependan de app.py.
"""

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
