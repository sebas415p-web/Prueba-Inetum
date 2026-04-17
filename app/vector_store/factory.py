"""
Módulo de Vector Store.

Patrón: Factory — VectorStoreFactory abstrae la creación del motor
de búsqueda vectorial. Cambiar de FAISS a ChromaDB solo requiere
modificar VECTOR_DB_TYPE en .env, sin refactorizar el código cliente.
"""
import os

from langchain_community.vectorstores import FAISS

from app.core.config import config
from app.core.logging_config import get_logger
from app.embeddings.embedder import get_embeddings

logger = get_logger(__name__)


class VectorStoreFactory:
    """
    Factory estático que crea o carga el vector store según configuración.
    Actualmente soporta FAISS. Agregar ChromaDB, Qdrant, etc. solo
    requiere añadir un nuevo `elif` sin tocar el resto del sistema.
    """

    @staticmethod
    def get_vector_store(store_type: str = None, texts: list[str] = None):
        """
        Args:
            store_type: Tipo de vector store ('faiss'). Default: config.vector_db_type
            texts:      Si se provee, crea un índice nuevo desde estos textos.
                        Si es None, carga el índice existente.

        Returns:
            Instancia del vector store lista para similarity_search().

        Raises:
            ValueError: Si el tipo no está soportado.
            FileNotFoundError: Si no existe índice y no se pasan textos.
        """
        store_type = store_type or config.vector_db_type
        embeddings = get_embeddings()

        if store_type == "faiss":
            if texts:
                return VectorStoreFactory._build_faiss(texts, embeddings)
            return VectorStoreFactory._load_faiss(embeddings)

        raise ValueError(
            f"Vector store '{store_type}' no soportado. "
            "Opciones disponibles: ['faiss']"
        )

    @staticmethod
    def _build_faiss(texts: list[str], embeddings) -> FAISS:
        logger.info("Construyendo índice FAISS con %d chunks...", len(texts))
        store = FAISS.from_texts(texts, embeddings)
        os.makedirs(config.faiss_index_path, exist_ok=True)
        store.save_local(config.faiss_index_path)
        logger.info("Índice FAISS guardado en: %s", config.faiss_index_path)
        return store

    @staticmethod
    def _load_faiss(embeddings) -> FAISS:
        index_path = config.faiss_index_path
        if not os.path.exists(index_path):
            raise FileNotFoundError(
                f"No se encontró el índice FAISS en '{index_path}'. "
                "Ejecuta POST /scrape o el comando 'scrape' en la CLI."
            )
        logger.info("Cargando índice FAISS desde: %s", index_path)
        store = FAISS.load_local(
            index_path,
            embeddings,
            allow_dangerous_deserialization=True,
        )
        logger.info("Índice FAISS cargado correctamente.")
        return store
