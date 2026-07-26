"""Tests del RAG mínimo y rutas /documents."""

from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest

from app.schemas.domain import DocumentCreate, RetrievedChunk
from app.services.rag_service import CHUNK_MAX_CHARS, RagService
from app.tests.conftest import build_settings, client_for, StubStorage
from app.tests.fakes.supabase import FakeSupabaseClient


# --- Fixtures -----------------------------------------------------------------------

FAKE_DOC_ROW = {
    "id": "b0000000-0000-4000-8000-000000000001",
    "project_id": "b0000000-0000-4000-8000-000000000099",
    "commitment_id": "b0000000-0000-4000-8000-000000000098",
    "title": "Cláusula SLA",
    "content": "Penalización de 20000 USD por entrega tardía.",
    "source_type": "document",
    "source_url": "https://example.com/sla",
    "metadata": {},
    "created_at": "2026-07-20T00:00:00Z",
}


@pytest.fixture
def fake_client() -> FakeSupabaseClient:
    return FakeSupabaseClient()


@pytest.fixture
def rag(fake_client: FakeSupabaseClient) -> RagService:
    from app.repositories.domain import DocumentRepository
    repo = DocumentRepository(fake_client)
    return RagService(repo)


@pytest.fixture
def app_with_docs(fake_client: FakeSupabaseClient):
    from app.main import create_app
    from app.providers.registry import ProviderRegistry

    settings = build_settings()
    application = create_app(settings)
    storage = StubStorage(settings, fake_client)
    application.state.storage = storage
    application.state.providers = ProviderRegistry()
    return application


# --- Tests de RagService ------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_empty_query_returns_empty(rag: RagService):
    """Query vacía no toca la DB."""
    result = await rag.retrieve("")
    assert result == []


@pytest.mark.asyncio
async def test_retrieve_whitespace_query_returns_empty(rag: RagService):
    """Query de solo espacios no toca la DB."""
    result = await rag.retrieve("   ")
    assert result == []


@pytest.mark.asyncio
async def test_retrieve_fulltext_returns_chunks(
    fake_client: FakeSupabaseClient, rag: RagService
):
    """Recuperación exitosa devuelve RetrievedChunk con strategy=fulltext."""
    fake_client.for_table("documents").returns([FAKE_DOC_ROW])
    result = await rag.retrieve("penalización")
    assert len(result) == 1
    assert result[0].strategy == "fulltext"
    assert result[0].title == "Cláusula SLA"
    assert isinstance(result[0].document_id, UUID)


@pytest.mark.asyncio
async def test_retrieve_filters_by_project_id(
    fake_client: FakeSupabaseClient, rag: RagService
):
    """El filtro project_id se pasa al repositorio."""
    fake_client.for_table("documents").returns([FAKE_DOC_ROW])
    pid = UUID("b0000000-0000-4000-8000-000000000099")
    result = await rag.retrieve("test", project_id=pid)
    calls = fake_client.for_table("documents").calls
    eq_calls = [c for c in calls if c.method == "eq"]
    assert any(c.args == ("project_id", str(pid)) for c in eq_calls)


@pytest.mark.asyncio
async def test_retrieve_filters_by_commitment_id(
    fake_client: FakeSupabaseClient, rag: RagService
):
    """El filtro commitment_id se pasa al repositorio."""
    fake_client.for_table("documents").returns([FAKE_DOC_ROW])
    cid = UUID("b0000000-0000-4000-8000-000000000098")
    result = await rag.retrieve("test", commitment_id=cid)
    calls = fake_client.for_table("documents").calls
    eq_calls = [c for c in calls if c.method == "eq"]
    assert any(c.args == ("commitment_id", str(cid)) for c in eq_calls)


@pytest.mark.asyncio
async def test_retrieve_respects_limit(
    fake_client: FakeSupabaseClient, rag: RagService
):
    """El límite se pasa al repositorio."""
    fake_client.for_table("documents").returns([FAKE_DOC_ROW])
    await rag.retrieve("test", limit=3)
    calls = fake_client.for_table("documents").calls
    limit_calls = [c for c in calls if c.method == "limit"]
    assert any(c.args == (3,) for c in limit_calls)


@pytest.mark.asyncio
async def test_retrieve_strategy_is_fulltext(
    fake_client: FakeSupabaseClient, rag: RagService
):
    """strategy siempre es fulltext en el MVP."""
    fake_client.for_table("documents").returns([FAKE_DOC_ROW])
    result = await rag.retrieve("test")
    for chunk in result:
        assert chunk.strategy == "fulltext"


@pytest.mark.asyncio
async def test_retrieve_db_failure_returns_empty(
    fake_client: FakeSupabaseClient, rag: RagService
):
    """Fallo de DB no revienta la recuperación: devuelve []."""
    fake_client.for_table("documents").raises(RuntimeError("DB down"))
    result = await rag.retrieve("test")
    assert result == []


@pytest.mark.asyncio
async def test_retrieve_vector_returns_empty(rag: RagService):
    """_retrieve_vector devuelve [] sin pgvector."""
    result = rag._retrieve_vector("test", project_id=None, commitment_id=None, limit=5)
    assert result == []


@pytest.mark.asyncio
async def test_index_document_creates_row(
    fake_client: FakeSupabaseClient, rag: RagService
):
    """index_document crea un documento en el repositorio."""
    fake_client.for_table("documents").returns([FAKE_DOC_ROW])
    doc = DocumentCreate(
        title="Test Doc",
        content="Contenido corto",
        project_id=UUID("b0000000-0000-4000-8000-000000000099"),
    )
    result = await rag.index_document(doc)
    assert result.title == "Cláusula SLA"  # lo que devuelve el fake


@pytest.mark.asyncio
async def test_index_long_text_creates_multiple_chunks(
    fake_client: FakeSupabaseClient, rag: RagService
):
    """Texto largo se trocea en múltiples documentos."""
    long_text = "A" * (CHUNK_MAX_CHARS + 500)
    fake_client.for_table("documents").returns([FAKE_DOC_ROW])
    doc = DocumentCreate(title="Long", content=long_text)
    await rag.index_document(doc)
    # Debe haber más de una llamada insert
    insert_calls = fake_client.for_table("documents").calls_to("insert")
    assert len(insert_calls) >= 2


def test_chunk_text_short():
    """Texto corto produce un solo chunk."""
    chunks = RagService._chunk_text("Hola mundo")
    assert len(chunks) == 1
    assert chunks[0] == "Hola mundo"


def test_chunk_text_paragraphs():
    """Texto con párrafos se divide por párrafos."""
    text = "Párrafo uno.\n\nPárrafo dos.\n\nPárrafo tres."
    chunks = RagService._chunk_text(text)
    # Con CHUNK_MAX_CHARS=1500, estos tres párrafos caben en uno
    assert len(chunks) >= 1


def test_chunk_text_very_long():
    """Texto largo sin párrafos se parte en bloques de CHUNK_MAX_CHARS."""
    text = "X" * (CHUNK_MAX_CHARS * 3)
    chunks = RagService._chunk_text(text)
    assert len(chunks) == 3
    assert all(len(c) <= CHUNK_MAX_CHARS for c in chunks)


# --- Tests de rutas /documents ------------------------------------------------------


@pytest.mark.asyncio
async def test_post_document_returns_201(app_with_docs, fake_client: FakeSupabaseClient):
    """POST /documents crea y devuelve 201."""
    fake_client.for_table("documents").returns([FAKE_DOC_ROW])
    async with client_for(app_with_docs) as client:
        resp = await client.post("/documents", json={
            "title": "Test",
            "content": "Contenido de prueba",
        })
    assert resp.status_code == 201
    assert resp.json()["title"] == "Cláusula SLA"


@pytest.mark.asyncio
async def test_get_document_returns_200(app_with_docs, fake_client: FakeSupabaseClient):
    """GET /documents/{id} devuelve 200."""
    fake_client.for_table("documents").returns([FAKE_DOC_ROW])
    doc_id = FAKE_DOC_ROW["id"]
    async with client_for(app_with_docs) as client:
        resp = await client.get(f"/documents/{doc_id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_document_not_found(app_with_docs, fake_client: FakeSupabaseClient):
    """GET /documents/{id} devuelve 404 si no existe."""
    fake_client.for_table("documents").returns([])
    async with client_for(app_with_docs) as client:
        resp = await client.get(f"/documents/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search_documents_returns_200(app_with_docs, fake_client: FakeSupabaseClient):
    """GET /documents/search devuelve lista de chunks."""
    fake_client.for_table("documents").returns([FAKE_DOC_ROW])
    async with client_for(app_with_docs) as client:
        resp = await client.get("/documents/search", params={"q": "penalización"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["strategy"] == "fulltext"


@pytest.mark.asyncio
async def test_search_documents_empty_query(app_with_docs, fake_client: FakeSupabaseClient):
    """GET /documents/search con q vacía devuelve lista vacía."""
    async with client_for(app_with_docs) as client:
        resp = await client.get("/documents/search", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json() == []
