"""
Consulta pública de números telefónicos reportados (vishing).

GET /api/numeros/consultar?numero=3001234567
GET /api/numeros/3001234567
GET /api/numeros/fuentes

Devuelve el nivel de riesgo explicable del número, los reportes comunitarios,
las coincidencias con el registro de fuentes oficiales y la recomendación.
"""
from fastapi import APIRouter, HTTPException, Query, Request

from app.core.limite import limitar_por_ip
from app.services import numeros

router = APIRouter()


def _ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for") or
            (request.client.host if request.client else "")).split(",")[0].strip()


def _consultar(numero: str, request: Request) -> dict:
    limitar_por_ip(f"numero:{_ip(request) or 'desconocida'}")
    try:
        resultado = numeros.analizar_numero(numero)
    except numeros.NumeroInvalido as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {**resultado, "registro": numeros.fuentes_publicas()}


@router.get("/numeros/fuentes")
def fuentes(request: Request):
    """Metadatos del registro: cuántos números y de qué fuentes salen."""
    limitar_por_ip(f"numero-fuentes:{_ip(request) or 'desconocida'}")
    return numeros.fuentes_publicas()


@router.get("/numeros/consultar")
def consultar(request: Request, numero: str = Query(..., min_length=1, max_length=40)):
    return _consultar(numero, request)


@router.get("/numeros/{numero}")
def consultar_por_ruta(numero: str, request: Request):
    return _consultar(numero, request)
