"""
Módulo de configuración centralizada.
Patrón: Singleton — garantiza una única instancia con configuración
cargada una sola vez desde variables de entorno.
"""
import os
import logging
from dotenv import load_dotenv


class ConfigManager:
    """
    Singleton que centraliza todas las variables de configuración del sistema.
    Al usar __new__, la segunda llamada a ConfigManager() retorna la misma instancia.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            load_dotenv()
            cls._instance._load()
        return cls._instance

    def _load(self):
        # ── LLM ──────────────────────────────────────────
        self.groq_api_key: str = os.getenv("GROQ_API_KEY", "")
        self.llm_model: str = os.getenv("LLM_MODEL", "llama3-8b-8192")
        self.llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
        self.llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "512"))

        # ── Embeddings ────────────────────────────────────
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

        # ── Reranker ──────────────────────────────────────
        self.reranker_model: str = os.getenv(
            "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        self.reranker_top_k: int = int(os.getenv("RERANKER_TOP_K", "3"))
        self.retrieval_k: int = int(os.getenv("RETRIEVAL_K", "10"))

        # ── Vector Store ──────────────────────────────────
        self.vector_db_type: str = os.getenv("VECTOR_DB_TYPE", "faiss")
        self.faiss_index_path: str = os.getenv("FAISS_INDEX_PATH", "data/faiss_index")

        # ── Procesamiento ─────────────────────────────────
        self.chunk_size: int = int(os.getenv("CHUNK_SIZE", "500"))
        self.chunk_overlap_ratio: float = float(os.getenv("CHUNK_OVERLAP_RATIO", "0.1"))

        # ── Conversación ──────────────────────────────────
        self.history_k: int = int(os.getenv("HISTORY_K", "5"))
        self.db_path: str = os.getenv("DB_PATH", "data/db/chat_history.db")

        # ── Scraping ──────────────────────────────────────
        self.bbva_url: str = os.getenv("BBVA_URL", "https://www.bbva.com.co/")
        self.scrape_max_pages: int = int(os.getenv("SCRAPE_MAX_PAGES", "20"))
        self.scrape_timeout: int = int(os.getenv("SCRAPE_TIMEOUT", "15"))
        self.scrape_delay: float = float(os.getenv("SCRAPE_DELAY", "1.0"))

        # ── Datos ─────────────────────────────────────────
        self.raw_data_path: str = os.getenv("RAW_DATA_PATH", "data/raw")
        self.clean_data_path: str = os.getenv("CLEAN_DATA_PATH", "data/clean")

        # ── Logging ───────────────────────────────────────
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def validate(self) -> bool:
        """Valida que los campos críticos estén presentes."""
        if not self.groq_api_key:
            logging.error(
                "GROQ_API_KEY no configurada. Agrega tu clave en el archivo .env. "
                "Obtén una gratis en https://console.groq.com"
            )
            return False
        return True


# Instancia global — se importa directamente en todos los módulos
config = ConfigManager()
