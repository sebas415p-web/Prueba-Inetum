"""
Módulo de persistencia del historial de conversación.

Patrón: Repository — ChatRepository ofrece una interfaz de acceso a datos
independiente del motor de almacenamiento (SQLite hoy, PostgreSQL mañana).
La lógica de negocio (RAGPipeline, AnalyticsModule) nunca toca SQL directamente.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from app.core.config import config
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# Repository
# ─────────────────────────────────────────────────────────────

class ChatRepository:
    """
    Repositorio de mensajes de conversación.
    Maneja toda la interacción con la base de datos SQLite.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        """Context manager que garantiza cierre de conexión ante excepciones."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Crea las tablas si no existen."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT    NOT NULL,
                    role        TEXT    NOT NULL CHECK(role IN ('user','assistant','system')),
                    content     TEXT    NOT NULL,
                    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)")
        logger.debug("Base de datos inicializada en: %s", self.db_path)

    # ── Escritura ─────────────────────────────────────────────

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Persiste un mensaje. Valida el rol antes de insertar."""
        if role not in ("user", "assistant", "system"):
            raise ValueError(f"Rol inválido: '{role}'. Debe ser 'user', 'assistant' o 'system'.")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
        logger.debug("Mensaje guardado [%s/%s]: %d chars", session_id[:8], role, len(content))

    # ── Lectura ───────────────────────────────────────────────

    def get_history(self, session_id: str, k: int = None) -> list[dict]:
        """
        Retorna los últimos k mensajes de una sesión, ordenados cronológicamente
        (el más antiguo primero, listo para pasarle a un LLM).
        """
        k = k or config.history_k
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content FROM messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, k),
            ).fetchall()
        # Invertimos para orden cronológico ascendente
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def get_all_sessions(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT session_id FROM messages ORDER BY session_id"
            ).fetchall()
        return [r["session_id"] for r in rows]

    def get_all_messages(self) -> list[dict]:
        """Retorna todos los mensajes para análisis batch."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id, role, content, timestamp FROM messages ORDER BY timestamp ASC"
            ).fetchall()
        return [dict(r) for r in rows]
