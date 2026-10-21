"""Límite simple de solicitudes por IP (por instancia): evita que un script inunde el registro."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException

_LIMITE_POR_MINUTO = 12
_solicitudes: dict[str, deque] = defaultdict(deque)


def limitar_por_ip(ip: str):
    ahora = time.monotonic()
    cola = _solicitudes[ip]
    while cola and ahora - cola[0] > 60:
        cola.popleft()
    if len(cola) >= _LIMITE_POR_MINUTO:
        raise HTTPException(status_code=429, detail="Demasiados mensajes seguidos. Espera un minuto e inténtalo de nuevo.")
    cola.append(ahora)
