"""Rutas de documentos (RAG)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DomainRepositoriesDep
from app.schemas.domain import DocumentCreate, DocumentRead, RetrievedChunk
from app.services.rag_service import RagService

router = APIRouter(prefix="/documents", tags=["documents"])


def _rag(repos: DomainRepositoriesDep) -> RagService:
    return RagService(repos.documents)


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Indexar documento",
)
async def index_document(
    body: DocumentCreate,
    repos: DomainRepositoriesDep,
) -> DocumentRead:
    svc = _rag(repos)
    return await svc.index_document(body)


@router.get(
    "/search",
    response_model=list[RetrievedChunk],
    summary="Buscar documentos por texto",
)
async def search_documents(
    repos: DomainRepositoriesDep,
    q: str = Query(default="", description="Texto de búsqueda"),
    project_id: UUID | None = Query(default=None),
    commitment_id: UUID | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[RetrievedChunk]:
    svc = _rag(repos)
    return await svc.retrieve(q, project_id=project_id, commitment_id=commitment_id, limit=limit)


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Obtener documento por ID",
)
async def get_document(
    document_id: UUID,
    repos: DomainRepositoriesDep,
) -> DocumentRead:
    row = await repos.documents.get(document_id)
    if not row:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return DocumentRead.model_validate(row)
