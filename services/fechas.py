"""
Primitivas temporales compartidas.

La base actual persiste timestamps UTC sin información de zona
horaria. Esta función conserva ese contrato de forma explícita
sin utilizar datetime.utcnow(), obsoleto desde Python 3.12.
"""

from datetime import UTC, datetime


def ahora_utc_naive():
    """Devuelve la hora UTC actual sin tzinfo."""
    return datetime.now(UTC).replace(tzinfo=None)
