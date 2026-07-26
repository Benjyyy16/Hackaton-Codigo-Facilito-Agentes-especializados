from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class IntegrationProvider(str, Enum):
    JIRA = "jira"
    GITHUB = "github"
    NOTION = "notion"
    AWS = "aws"
    SLACK = "slack"
    VERCEL = "vercel"
    ERP = "erp"
    RIGHTWAY = "rightway"


class ConnectIntegrationRequest(BaseModel):
    """Credenciales que el usuario envía para vincular una integración."""
    credentials: dict = Field(..., description="Credenciales del provider (token, api_key, etc.)")
    config: dict = Field(default_factory=dict, description="Config extra (team_id, base_url, etc.)")


class IntegrationResponse(BaseModel):
    id: str
    user_id: str
    provider: str
    status: str
    config: dict
    created_at: str
    updated_at: str
