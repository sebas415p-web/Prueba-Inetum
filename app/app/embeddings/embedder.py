"""
Módulo de embeddings.
Encapsula la creación del modelo de embeddings para desacoplarlo
del vector store. Permite sustituir el modelo sin tocar la lógica
de indexación o búsqueda.
"""
from langchain_community.embeddings import HuggingFaceEmbeddings

from app.core.config import config
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Cache del modelo para evitar cargarlo varias veces en la misma sesión
_embeddings_cache: HuggingFaceEmbeddings | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Retorna la instancia del modelo de embeddings.
    Usa un módulo-level cache para no recargar pesos en cada llamada.
    """
    global _embeddings_cache
    if _embeddings_cache is None:
        logger.info("Cargando modelo de embeddings: %s", config.embedding_model)
        _embeddings_cache = HuggingFaceEmbeddings(
            model_name=config.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("Modelo de embeddings cargado.")
    return _embeddings_cache
