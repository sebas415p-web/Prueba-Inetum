"""
Pipeline RAG principal.
Usa requests directamente para llamar a la API de Groq,
evitando conflictos de versiones con httpx/groq library.
"""
from __future__ import annotations

import requests

from app.chat.memory import ChatRepository
from app.core.config import config
from app.core.logging_config import get_logger
from app.vector_store.factory import VectorStoreFactory
from sentence_transformers import CrossEncoder

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "Eres un asistente experto en productos y servicios de BBVA Colombia. "
    "Responde ÚNICAMENTE basándote en el contexto proporcionado. "
    "Si la información no está en el contexto, dilo claramente. "
    "Responde siempre en español, de forma clara y concisa."
)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class RAGPipeline:
    def __init__(self):
        if not config.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY no configurada. Agrégala en el .env y reinicia."
            )
        logger.info("Inicializando RAGPipeline...")
        self.vector_store = VectorStoreFactory.get_vector_store()
        self.repo = ChatRepository()
        logger.info("Cargando reranker: %s", config.reranker_model)
        self.reranker = CrossEncoder(config.reranker_model)
        logger.info("RAGPipeline listo. LLM: %s", config.llm_model)

    def generate_response(self, session_id: str, query: str) -> str:
        # 1. Recuperación
        docs = self._retrieve(query)
        if not docs:
            return "No encontré información relevante. Intenta reformular tu pregunta."

        # 2. Reranking
        context = self._rerank(query, docs)

        # 3. Historial
        history = self.repo.get_history(session_id)

        # 4. Llamada al LLM
        response = self._call_groq(history, context, query)

        # 5. Persistir
        self.repo.add_message(session_id, "user", query)
        self.repo.add_message(session_id, "assistant", response)

        return response

    def _retrieve(self, query: str) -> list:
        try:
            docs = self.vector_store.similarity_search(query, k=config.retrieval_k)
            logger.debug("Recuperados %d docs", len(docs))
            return docs
        except Exception as e:
            logger.error("Error en búsqueda vectorial: %s", e)
            return []

    def _rerank(self, query: str, docs: list) -> str:
        try:
            pairs = [[query, d.page_content] for d in docs]
            scores = self.reranker.predict(pairs)
            ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
            top = [d for _, d in ranked[:config.reranker_top_k]]
            return "\n\n---\n\n".join(d.page_content for d in top)
        except Exception as e:
            logger.warning("Reranker falló, usando orden original: %s", e)
            return "\n\n---\n\n".join(d.page_content for d in docs[:config.reranker_top_k])

    def _call_groq(self, history: list[dict], context: str, query: str) -> str:
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({
            "role": "user",
            "content": f"Contexto de BBVA Colombia:\n{context}\n\nPregunta: {query}"
        })

        headers = {
            "Authorization": f"Bearer {config.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.llm_model,
            "messages": messages,
            "temperature": config.llm_temperature,
            "max_tokens": config.llm_max_tokens,
        }

        try:
            resp = requests.post(
                GROQ_API_URL,
                headers=headers,
                json=payload,
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            response = data["choices"][0]["message"]["content"]
            logger.debug("Respuesta generada: %d chars", len(response))
            return response
        except requests.exceptions.Timeout:
            logger.error("Timeout llamando a Groq API")
            return "Timeout al conectar con el modelo. Intenta nuevamente."
        except requests.exceptions.HTTPError as e:
            logger.error("Error HTTP Groq: %s | %s", e, resp.text)
            if resp.status_code == 401:
                return "API Key de Groq inválida. Verifica tu .env."
            if resp.status_code == 429:
                return "Límite de requests de Groq alcanzado. Espera un momento."
            return f"Error del servidor Groq ({resp.status_code}). Intenta nuevamente."
        except Exception as e:
            logger.error("Error inesperado llamando a Groq: %s", e)
            return "Error al generar respuesta. Verifica tu conexión."
