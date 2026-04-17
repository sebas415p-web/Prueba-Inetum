"""API REST del BBVA RAG Assistant."""
from __future__ import annotations
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.analytics.analyzer import AnalyticsModule
from app.chat.memory import ChatRepository
from app.core.config import config
from app.core.logging_config import get_logger, setup_logging
from app.processing.processor import TextProcessor
from app.scraping.scraper import (
    BBVAScraper, BBVAProductScraper, MultiPageBBVAScraper, ScraperContext
)
from app.vector_store.factory import VectorStoreFactory

setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="BBVA RAG Assistant",
    description="Sistema RAG conversacional para consultar información de BBVA Colombia.",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

rag_pipeline = None


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)

class ChatResponse(BaseModel):
    session_id: str
    query: str
    response: str

class ScrapeRequest(BaseModel):
    url: Optional[str] = None
    mode: str = Field("products", description="'products' | 'single' | 'multi'")

class ScrapeResponse(BaseModel):
    status: str
    url: str
    pages_scraped: int
    chunks_generated: int
    message: str


@app.on_event("startup")
def startup_event():
    global rag_pipeline
    logger.info("Iniciando BBVA RAG Assistant v1.0.0")
    if not config.validate():
        return
    try:
        from app.rag.pipeline import RAGPipeline
        rag_pipeline = RAGPipeline()
        logger.info("RAG Pipeline listo.")
    except FileNotFoundError:
        logger.warning("Índice no encontrado. Ejecuta POST /scrape primero.")
    except Exception as e:
        logger.error("Error inicializando pipeline: %s", e)


@app.get("/health", tags=["Sistema"])
def health():
    return {
        "status": "ok",
        "rag_ready": rag_pipeline is not None,
        "config": {
            "llm_model": config.llm_model,
            "embedding_model": config.embedding_model,
            "vector_db": config.vector_db_type,
            "history_k": config.history_k,
        },
    }


@app.post("/scrape", response_model=ScrapeResponse, tags=["Indexación"])
def scrape(request: ScrapeRequest = None):
    """
    Modos disponibles:
    - 'products' (default): scrapea 33 páginas de productos BBVA directamente. RECOMENDADO.
    - 'single': solo la página principal.
    - 'multi': crawling recursivo.
    """
    global rag_pipeline
    url = (request.url if request and request.url else None) or config.bbva_url
    mode = request.mode if request else "products"

    try:
        if mode == "products":
            strategy = BBVAProductScraper()
        elif mode == "multi":
            strategy = MultiPageBBVAScraper()
        else:
            strategy = BBVAScraper()

        scraper = ScraperContext(strategy)
        raw_text = scraper.execute_scraping(url)

        if not raw_text:
            raise HTTPException(status_code=502, detail="El scraping no retornó contenido.")

        processor = TextProcessor()
        clean_text = processor.clean(raw_text)
        chunks = processor.chunk(clean_text)

        if not chunks:
            raise HTTPException(status_code=422, detail="No se generaron chunks.")

        VectorStoreFactory.get_vector_store(texts=chunks)

        from app.rag.pipeline import RAGPipeline
        rag_pipeline = RAGPipeline()

        pages = len(strategy._scraped) if hasattr(strategy, "_scraped") else (
            len(strategy._visited) if hasattr(strategy, "_visited") else 1
        )

        return ScrapeResponse(
            status="ok",
            url=url,
            pages_scraped=pages,
            chunks_generated=len(chunks),
            message=f"Índice creado con {len(chunks)} chunks de {pages} páginas.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error en /scrape: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat", response_model=ChatResponse, tags=["Conversación"])
def chat(request: ChatRequest):
    if rag_pipeline is None:
        raise HTTPException(status_code=503, detail="RAG no inicializado. Ejecuta POST /scrape primero.")
    try:
        response = rag_pipeline.generate_response(request.session_id, request.query)
        return ChatResponse(session_id=request.session_id, query=request.query, response=response)
    except Exception as e:
        logger.exception("Error en /chat: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/{session_id}", tags=["Conversación"])
def get_history(session_id: str):
    repo = ChatRepository()
    messages = repo.get_history(session_id, k=1000)
    return {"session_id": session_id, "messages": messages}


@app.get("/sessions", tags=["Conversación"])
def list_sessions():
    return {"sessions": ChatRepository().get_all_sessions()}


@app.get("/analytics", tags=["Analytics"])
def analytics():
    return AnalyticsModule().get_metrics()
