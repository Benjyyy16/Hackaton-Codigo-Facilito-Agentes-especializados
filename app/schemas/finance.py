from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class ERPProvider(str, Enum):
    SAP = "sap"
    ORACLE = "oracle"
    ODOO = "odoo"
    QUICKBOOKS = "quickbooks"
    XERO = "xero"
    CUSTOM = "custom"


class ERPConnectRequest(BaseModel):
    provider: ERPProvider
    base_url: str = Field(..., description="URL base del ERP")
    api_key: str = Field(..., description="API key o token del ERP")
    company_id: str | None = None
    extra: dict = Field(default_factory=dict)


class FinancialRecord(BaseModel):
    date: str
    concept: str
    amount: float
    currency: str = "USD"
    category: str | None = None
    reference: str | None = None


class FinancialSummary(BaseModel):
    source: str
    records: list[FinancialRecord]
    total_income: float = 0.0
    total_expenses: float = 0.0
    net: float = 0.0
    currency: str = "USD"
    rows_processed: int = 0
    errors: list[str] = Field(default_factory=list)
