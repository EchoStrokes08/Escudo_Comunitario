"""
Vista para autoridades y organizaciones comunitarias (Policía, Fiscalía, JAC).

GET /api/autoridades/casos[?formato=csv]   Authorization: Bearer <AUTORIDADES_TOKEN>

Entrega los casos completos (mensaje original, indicadores sin enmascarar,
certificado) para investigar y actuar de forma coordinada. Nunca incluye el
teléfono de la víctima: solo su seudónimo.
"""
import csv
import io

from fastapi import APIRouter, Header, HTTPException, Response

from app.core.config import settings
from app.services import firebase_db

router = APIRouter()

_COLUMNAS = ["fecha", "certificado", "altura", "canal", "upz", "nivel_riesgo", "confianza", "tipo_fraude",
             "entidad_suplantada", "indicadores", "mensaje_original", "texto_detectado", "reportante", "motor"]


def _autorizar(authorization: str):
    if not settings.AUTORIDADES_TOKEN:
        raise HTTPException(status_code=503, detail="La vista de autoridades no está configurada (AUTORIDADES_TOKEN).")
    if authorization != f"Bearer {settings.AUTORIDADES_TOKEN}":
        raise HTTPException(status_code=401, detail="Token inválido")


@router.get("/autoridades/casos")
def casos(formato: str = "json", limite: int = 500, authorization: str = Header("")):
    _autorizar(authorization)
    casos = firebase_db.casos_completos(min(max(limite, 1), 2000))
    # Los documentos anteriores a la v2 podían guardar el teléfono: nunca se exporta
    for caso in casos:
        caso.pop("telefono", None)

    if formato == "csv":
        salida = io.StringIO()
        escritor = csv.DictWriter(salida, fieldnames=_COLUMNAS, extrasaction="ignore")
        escritor.writeheader()
        for caso in casos:
            fila = dict(caso)
            fila["indicadores"] = "; ".join(f"{i.get('tipo')}:{i.get('valor')}" for i in caso.get("indicadores", []))
            escritor.writerow(fila)
        return Response(
            content="﻿" + salida.getvalue(), media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="casos-escudo-comunitario.csv"'},
        )
    return {"total": len(casos), "casos": casos}
