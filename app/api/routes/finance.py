from __future__ import annotations
from fastapi import APIRouter, HTTPException, UploadFile, File, status
from app.schemas.finance import ERPConnectRequest, FinancialSummary
from app.services.finance_service import connect_erp, parse_excel_bytes

router = APIRouter(prefix="/finance", tags=["finance"])

MAX_FILE_MB = 10


@router.post(
    "/erp",
    response_model=FinancialSummary,
    status_code=status.HTTP_200_OK,
    summary="Conectar con ERP",
    description="Conecta con SAP, Oracle, Odoo, QuickBooks, Xero u otro ERP y obtiene registros financieros.",
)
async def erp_connect(req: ERPConnectRequest) -> FinancialSummary:
    """
    **Providers soportados:** sap, oracle, odoo, quickbooks, xero, custom

    Envía credenciales y URL del ERP, recibe registros normalizados.
    """
    try:
        return await connect_erp(req)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post(
    "/upload",
    response_model=FinancialSummary,
    status_code=status.HTTP_200_OK,
    summary="Subir Excel o CSV financiero",
    description="Acepta .csv, .xlsx o .xls con datos financieros y devuelve resumen normalizado.",
)
async def upload_file(file: UploadFile = File(...)) -> FinancialSummary:
    """
    **Columnas reconocidas:** fecha/date, concepto/description, monto/amount, moneda/currency, categoria/category

    Máximo 10 MB.
    """
    if not file.filename or not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=415, detail="Solo se aceptan .csv, .xlsx o .xls")

    content = await file.read()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Archivo excede {MAX_FILE_MB} MB")

    return parse_excel_bytes(content, file.filename.lower())
