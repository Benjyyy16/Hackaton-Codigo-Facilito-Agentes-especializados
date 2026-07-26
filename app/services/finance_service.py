from __future__ import annotations
import io
import csv
from app.schemas.finance import ERPConnectRequest, FinancialRecord, FinancialSummary
from app.core.logging import get_logger

logger = get_logger("finance")


async def connect_erp(req: ERPConnectRequest) -> FinancialSummary:
    """Conecta con un ERP y obtiene registros financieros."""
    import httpx
    records: list[FinancialRecord] = []
    errors: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {req.api_key}"}
            # Endpoint genérico — cada ERP tiene su propio path
            paths = {
                "sap": "/api/v1/financials",
                "oracle": "/fscmRestApi/resources/11.13.18.05/ledgerBalances",
                "odoo": "/api/account.move",
                "quickbooks": "/v3/company/{company}/reports/ProfitAndLoss",
                "xero": "/api.xro/2.0/Reports/ProfitAndLoss",
                "custom": "/financials",
            }
            path = paths.get(req.provider.value, "/financials")
            if "{company}" in path and req.company_id:
                path = path.replace("{company}", req.company_id)

            r = await client.get(f"{req.base_url.rstrip('/')}{path}", headers=headers)
            r.raise_for_status()
            data = r.json()

            # Parseo genérico — adaptar por ERP
            items = data if isinstance(data, list) else data.get("value", data.get("records", []))
            for item in items[:500]:
                records.append(FinancialRecord(
                    date=str(item.get("date", item.get("Date", ""))),
                    concept=str(item.get("description", item.get("Name", ""))),
                    amount=float(item.get("amount", item.get("Amount", 0))),
                    currency=item.get("currency", "USD"),
                    category=item.get("category", item.get("AccountType")),
                    reference=str(item.get("id", item.get("Id", ""))),
                ))
    except Exception as e:
        errors.append(str(e))
        logger.error("ERP connect error: %s", e)

    return _summarize(req.provider.value, records, errors)


def parse_excel_bytes(content: bytes, filename: str) -> FinancialSummary:
    """Parsea un Excel o CSV y devuelve registros financieros."""
    records: list[FinancialRecord] = []
    errors: list[str] = []

    try:
        if filename.endswith(".csv"):
            text = content.decode("utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            for i, row in enumerate(reader):
                if i >= 5000:
                    break
                try:
                    records.append(_row_to_record(row))
                except Exception as e:
                    errors.append(f"Fila {i+2}: {e}")

        elif filename.endswith((".xlsx", ".xls")):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
                ws = wb.active
                headers_row = [str(c.value or "").strip().lower() for c in next(ws.iter_rows(min_row=1, max_row=1))]
                for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
                    if i >= 5000:
                        break
                    d = dict(zip(headers_row, row))
                    try:
                        records.append(_row_to_record(d))
                    except Exception as e:
                        errors.append(f"Fila {i+2}: {e}")
            except ImportError:
                errors.append("Instala openpyxl para leer .xlsx")
        else:
            errors.append("Formato no soportado. Usa .csv, .xlsx o .xls")

    except Exception as e:
        errors.append(str(e))

    return _summarize(filename, records, errors)


def _row_to_record(row: dict) -> FinancialRecord:
    # Columnas comunes en español e inglés
    date = row.get("fecha") or row.get("date") or row.get("Date") or ""
    concept = row.get("concepto") or row.get("description") or row.get("Description") or row.get("concept") or ""
    amount_raw = row.get("monto") or row.get("amount") or row.get("Amount") or row.get("importe") or 0
    currency = row.get("moneda") or row.get("currency") or "USD"
    category = row.get("categoria") or row.get("category") or row.get("tipo") or row.get("type")
    reference = row.get("referencia") or row.get("reference") or row.get("id") or row.get("ID")
    return FinancialRecord(
        date=str(date),
        concept=str(concept),
        amount=float(str(amount_raw).replace(",", ".") or 0),
        currency=str(currency),
        category=str(category) if category else None,
        reference=str(reference) if reference else None,
    )


def _summarize(source: str, records: list[FinancialRecord], errors: list[str]) -> FinancialSummary:
    income = sum(r.amount for r in records if r.amount > 0)
    expenses = sum(r.amount for r in records if r.amount < 0)
    return FinancialSummary(
        source=source,
        records=records,
        total_income=round(income, 2),
        total_expenses=round(abs(expenses), 2),
        net=round(income + expenses, 2),
        rows_processed=len(records),
        errors=errors,
    )
