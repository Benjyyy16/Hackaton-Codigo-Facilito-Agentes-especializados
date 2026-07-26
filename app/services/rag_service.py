"""RAG mínimo sobre Supabase.

LIMITACIONES:
- La recuperación es textual (ilike). No usa embeddings ni pgvector.
  La precisión es inferior a un RAG vectorial, pero funciona sin extensiones
  adicionales en Supabase y no bloquea el MVP.
- El chunking es por párrafos con solape 0. Textos sin saltos de línea se parten
  en bloques de ~1500 caracteres (aprox. 375 tokens). El límite se eligió para que
  cada chunk quepa en el contexto del LLM sin truncar información relevante.
- No hay re-ranking ni filtro por score mínimo: todos los resultados devueltos por
  ilike se consideran relevantes.
"""

from __future__ import annotations

from uuid import UUID

from app.core.logging import get_logger
from app.repositories.domain import DocumentRepository
from app.schemas.domain import DocumentCreate, DocumentRead, RetrievedChunk

logger = get_logger("service.rag")

#: Tamaño máximo de un chunk en caracteres. ~375 tokens GPT-4. Se eligió para que
#: quepa en contexto sin truncar y cubra un párrafo promedio de documento legal/técnico.
CHUNK_MAX_CHARS: int = 1500


class RagService:
    """Servicio de indexación y recuperación documental.

    Estrategia por defecto: fulltext (ilike sobre content).
    Interfaz preparada para pgvector cuando la extensión esté disponible.
    """

    def __init__(self, documents: DocumentRepository) -> None:
        self._documents = documents

    # --- Indexación -----------------------------------------------------------------

    async def index_document(self, doc: DocumentCreate) -> DocumentRead:
        """Indexa un documento. Si el contenido supera CHUNK_MAX_CHARS, lo trocea
        por párrafos y crea un documento por chunk.

        Devuelve el primer documento creado (el "padre" lógico).
        """
        chunks = self._chunk_text(doc.content)

        first: DocumentRead | None = None
        for i, chunk in enumerate(chunks):
            payload = doc.model_dump(mode="json")
            payload["content"] = chunk
            # Título diferenciado para chunks secundarios
            if i > 0:
                payload["title"] = f"{doc.title} [parte {i + 1}]"

            row = await self._documents.create(payload)
            parsed = DocumentRead.model_validate(row)
            if first is None:
                first = parsed

        # Siempre hay al menos un chunk
        assert first is not None  # noqa: S101
        return first

    # --- Recuperación ---------------------------------------------------------------

    async def retrieve(
        self,
        query: str,
        *,
        project_id: UUID | None = None,
        commitment_id: UUID | None = None,
        limit: int = 5,
    ) -> list[RetrievedChunk]:
        """Recupera documentos relevantes usando búsqueda textual.

        Si la query está vacía, devuelve lista vacía sin consultar la DB.
        """
        if not query or not query.strip():
            return []

        try:
            rows = await self._retrieve_fulltext(
                query, project_id=project_id, commitment_id=commitment_id, limit=limit
            )
        except Exception as error:  # noqa: BLE001 — el RAG no debe tumbar al consumidor
            logger.warning("Recuperación RAG fallida: %s", type(error).__name__)
            return []

        # Si fulltext no devuelve nada, intentar vector (hoy devuelve [])
        if not rows:
            return self._retrieve_vector(
                query, project_id=project_id, commitment_id=commitment_id, limit=limit
            )

        return [
            RetrievedChunk(
                document_id=UUID(row["id"]) if row.get("id") else None,
                title=row.get("title", ""),
                content=row.get("content", "")[:2000],
                score=1.0,  # ilike no produce score numérico
                strategy="fulltext",
                source_url=row.get("source_url"),
            )
            for row in rows
        ]

    # --- Estrategias privadas -------------------------------------------------------

    async def _retrieve_fulltext(
        self,
        query: str,
        *,
        project_id: UUID | None = None,
        commitment_id: UUID | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Delegado directo a DocumentRepository.search_fulltext."""
        return await self._documents.search_fulltext(
            query, project_id=project_id, commitment_id=commitment_id, limit=limit
        )

    def _retrieve_vector(
        self,
        query: str,  # noqa: ARG002
        *,
        project_id: UUID | None = None,  # noqa: ARG002
        commitment_id: UUID | None = None,  # noqa: ARG002
        limit: int = 5,  # noqa: ARG002
    ) -> list[RetrievedChunk]:
        """Recuperación por embeddings con pgvector.

        Devuelve [] porque pgvector es OPCIONAL y no está habilitado en el MVP.
        Cuando se active:
        1. Generar embedding del query con el modelo configurado.
        2. Buscar los K vecinos más cercanos en la columna `embedding` de documents.
        3. Devolver RetrievedChunk con strategy="vector".

        La interfaz existe para que el consumidor no cambie cuando se implemente.
        """
        return []

    # --- Chunking -------------------------------------------------------------------

    @staticmethod
    def _chunk_text(text: str) -> list[str]:
        """Divide texto en chunks por párrafos, sin solape.

        Si un párrafo excede CHUNK_MAX_CHARS, se parte en bloques de ese tamaño.
        Nunca devuelve una lista vacía: un texto vacío produce un chunk vacío.
        """
        if not text.strip():
            return [text]

        paragraphs = text.split("\n\n")
        chunks: list[str] = []
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Si el párrafo solo cabe cortado
            if len(para) > CHUNK_MAX_CHARS:
                # Flush lo acumulado
                if current:
                    chunks.append(current.strip())
                    current = ""
                # Partir el párrafo grande
                for i in range(0, len(para), CHUNK_MAX_CHARS):
                    chunks.append(para[i : i + CHUNK_MAX_CHARS])
                continue

            # ¿Cabe en el chunk actual?
            candidate = f"{current}\n\n{para}" if current else para
            if len(candidate) <= CHUNK_MAX_CHARS:
                current = candidate
            else:
                chunks.append(current.strip())
                current = para

        if current.strip():
            chunks.append(current.strip())

        return chunks if chunks else [text]
