from __future__ import annotations
from fastapi import APIRouter, HTTPException, UploadFile, File, status
from app.providers.finance import FinanceProvider
from app.schemas.finance import ERPConnectRequest, FinancialSummary
from app.schemas.finance_domain import (
    FinanceAnalysis,
    FinanceImportReport,
    FinanceImportRequest,
    FinanceSnapshot,
)
from app.services import finance_analysis_service
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


# ---------------------------------------------------------------------------------
# Dominio Datgent: importación y análisis del snapshot financiero
#
# Estos dos endpoints trabajan con ``FinanceSnapshot``, el modelo del dominio con
# ``Decimal``, y no con ``FinancialSummary``, que usa ``float`` y se conserva para el
# flujo heredado de ERP y Excel. Mezclar los dos modelos en un mismo endpoint obligaría
# a convertir entre ellos, y toda conversión de dinero a binario es una pérdida.
# ---------------------------------------------------------------------------------


@router.post(
    "/import",
    response_model=FinanceImportReport,
    status_code=status.HTTP_200_OK,
    summary="Importar snapshot financiero (JSON o CSV)",
    description=(
        "Valida y carga un snapshot financiero del dominio: líneas de presupuesto, horas "
        "imputadas, penalizaciones contractuales y pagos retenidos.\n\n"
        "Acepta `json_data` o `csv_content`, no ambos. El resultado incluye el análisis "
        "determinístico ya calculado."
    ),
    responses={
        200: {"description": "Snapshot válido, con su análisis"},
        422: {"description": "Los datos no validan; el informe detalla los errores"},
    },
)
async def import_finance(request: FinanceImportRequest) -> FinanceImportReport:
    """Importa y analiza un snapshot financiero.

    Un fallo de validación devuelve 200 con ``success=False`` y los errores detallados,
    no un 422 vacío: quien importa un fichero necesita saber qué fila lo rompió.
    """
    provider = FinanceProvider()

    try:
        if request.json_data is not None:
            snapshot = provider.load_from_json(request.json_data)
        elif request.csv_content is not None:
            snapshot = provider.load_from_csv(request.csv_content)
        else:
            return FinanceImportReport(
                success=False,
                errors=["Se requiere 'json_data' o 'csv_content'."],
            )
    except Exception as error:  # noqa: BLE001 - frontera de validación
        return FinanceImportReport(
            success=False, errors=[f"{type(error).__name__}: {error}"]
        )

    analysis = finance_analysis_service.analyze(snapshot)
    return FinanceImportReport(success=True, snapshot=snapshot, analysis=analysis)


@router.post(
    "/analyze",
    response_model=FinanceAnalysis,
    status_code=status.HTTP_200_OK,
    summary="Analizar un snapshot financiero ya validado",
    description=(
        "Ejecuta el cálculo determinístico sobre un snapshot: desviación de presupuesto, "
        "coste de mano de obra, margen, burn rate, exposición por penalización y "
        "exposición total, con los hallazgos y la evidencia que los respaldan.\n\n"
        "El cálculo es reproducible: los mismos datos producen siempre el mismo resultado."
    ),
)
async def analyze_finance(snapshot: FinanceSnapshot) -> FinanceAnalysis:
    """Analiza un snapshot financiero.

    No persiste nada: es un cálculo puro. Existe separado de ``/import`` para poder
    reanalizar sin volver a cargar el fichero.
    """
    return finance_analysis_service.analyze(snapshot)
