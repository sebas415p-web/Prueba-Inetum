"""
Módulo de Analytics.
Recorre el historial de conversaciones y extrae métricas de uso e impacto.
Incluye análisis de frecuencia de temas (palabras clave) sin dependencias externas.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta

from app.chat.memory import ChatRepository
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Stopwords en español para el análisis de temas
_STOPWORDS = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las",
    "un", "por", "con", "una", "su", "para", "es", "al", "lo", "como",
    "más", "pero", "sus", "le", "ya", "o", "fue", "este", "ha", "si",
    "me", "mi", "son", "sin", "sobre", "ser", "tiene", "le", "muy",
    "hay", "donde", "quien", "cual", "eso", "esto", "esa", "ese",
    "cuál", "qué", "cómo", "cuándo", "dónde", "no", "sí", "también",
    "puede", "puedo", "quiero", "tienen", "tengo", "hacer", "cuáles",
}


class AnalyticsModule:
    """
    Extrae métricas clave del historial de conversaciones.

    Métricas disponibles:
    - total_queries: número total de preguntas hechas por usuarios
    - unique_sessions: sesiones únicas
    - avg_query_length_chars: longitud media de las preguntas
    - avg_queries_per_session: promedio de consultas por sesión
    - most_active_session: sesión con más mensajes
    - queries_last_7_days: uso diario de los últimos 7 días
    - top_keywords: palabras clave más frecuentes en las preguntas
    - topic_distribution: agrupación temática simplificada
    - response_length_avg: longitud media de las respuestas del bot
    - activity_by_hour: distribución de consultas por hora del día
    """

    def __init__(self, db_path: str = None):
        self._repo = ChatRepository(db_path) if db_path else ChatRepository()

    # ─── Punto de entrada principal ──────────────────────────

    def get_metrics(self) -> dict:
        """Retorna el diccionario completo de métricas."""
        try:
            messages = self._repo.get_all_messages()
            if not messages:
                return {"message": "No hay conversaciones registradas aún."}

            user_msgs = [m for m in messages if m["role"] == "user"]
            bot_msgs  = [m for m in messages if m["role"] == "assistant"]

            return {
                **self._basic_metrics(user_msgs, bot_msgs),
                **self._session_metrics(user_msgs),
                **self._temporal_metrics(user_msgs),
                **self._text_metrics(user_msgs, bot_msgs),
            }
        except Exception as e:
            logger.exception("Error al calcular métricas: %s", e)
            return {"error": str(e)}

    # ─── Métricas básicas ─────────────────────────────────────

    @staticmethod
    def _basic_metrics(user_msgs: list[dict], bot_msgs: list[dict]) -> dict:
        total = len(user_msgs)
        sessions = {m["session_id"] for m in user_msgs}
        avg_q_len = (
            round(sum(len(m["content"]) for m in user_msgs) / total, 1) if total else 0
        )
        avg_r_len = (
            round(sum(len(m["content"]) for m in bot_msgs) / len(bot_msgs), 1)
            if bot_msgs else 0
        )
        return {
            "total_queries": total,
            "total_responses": len(bot_msgs),
            "unique_sessions": len(sessions),
            "avg_query_length_chars": avg_q_len,
            "avg_response_length_chars": avg_r_len,
        }

    # ─── Métricas por sesión ──────────────────────────────────

    @staticmethod
    def _session_metrics(user_msgs: list[dict]) -> dict:
        sessions = {m["session_id"] for m in user_msgs}
        counts = Counter(m["session_id"] for m in user_msgs)
        most_active_id = counts.most_common(1)[0] if counts else (None, 0)
        avg_per_session = (
            round(len(user_msgs) / len(sessions), 2) if sessions else 0
        )
        return {
            "avg_queries_per_session": avg_per_session,
            "most_active_session": {
                "session_id": most_active_id[0],
                "query_count": most_active_id[1],
            },
        }

    # ─── Métricas temporales ──────────────────────────────────

    @staticmethod
    def _temporal_metrics(user_msgs: list[dict]) -> dict:
        # Agrupa por día (últimos 7 días)
        daily: Counter = Counter()
        hourly: Counter = Counter()

        for m in user_msgs:
            try:
                ts = datetime.fromisoformat(m["timestamp"])
                daily[ts.strftime("%Y-%m-%d")] += 1
                hourly[ts.hour] += 1
            except (ValueError, TypeError):
                pass

        cutoff = datetime.utcnow() - timedelta(days=6)
        last_7 = []
        for i in range(7):
            day = (cutoff + timedelta(days=i)).strftime("%Y-%m-%d")
            last_7.append({"date": day, "queries": daily.get(day, 0)})

        hour_dist = [
            {"hour": f"{h:02d}:00", "queries": hourly.get(h, 0)}
            for h in range(24)
            if hourly.get(h, 0) > 0
        ]

        return {
            "queries_last_7_days": last_7,
            "activity_by_hour": hour_dist,
        }

    # ─── Análisis de texto / temas ────────────────────────────

    @staticmethod
    def _text_metrics(user_msgs: list[dict], bot_msgs: list[dict]) -> dict:
        # Tokenizar y filtrar stopwords
        all_words: list[str] = []
        for m in user_msgs:
            tokens = re.findall(r"\b[a-záéíóúñü]{4,}\b", m["content"].lower())
            all_words.extend(t for t in tokens if t not in _STOPWORDS)

        word_freq = Counter(all_words)
        top_keywords = [
            {"keyword": kw, "count": cnt}
            for kw, cnt in word_freq.most_common(15)
        ]

        # Agrupación temática simplificada con categorías predefinidas
        topics = _classify_topics(user_msgs)

        return {
            "top_keywords": top_keywords,
            "topic_distribution": topics,
        }


# ─── Clasificador de temas por palabras clave ──────────────────

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "Tarjetas de crédito": ["tarjeta", "crédito", "débito", "visa", "mastercard", "cuota"],
    "Cuentas bancarias": ["cuenta", "ahorro", "corriente", "apertura", "saldo"],
    "Préstamos y créditos": ["préstamo", "crédito", "hipoteca", "interés", "cuota", "financiación"],
    "Inversiones": ["inversión", "cdts", "fondos", "rentabilidad", "plazo", "fijo"],
    "Banca digital": ["app", "digital", "online", "transferencia", "pago", "bbva"],
    "Seguros": ["seguro", "protección", "cobertura", "póliza", "vida"],
    "Sucursales y ATMs": ["cajero", "sucursal", "oficina", "horario", "atención"],
}


def _classify_topics(user_msgs: list[dict]) -> list[dict]:
    """
    Clasifica cada mensaje en uno de los temas predefinidos basándose
    en presencia de palabras clave. Un mensaje puede pertenecer a varios temas.
    """
    topic_counts: Counter = Counter()
    for m in user_msgs:
        text = m["content"].lower()
        for topic, keywords in _TOPIC_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                topic_counts[topic] += 1

    total = sum(topic_counts.values()) or 1
    return [
        {
            "topic": topic,
            "count": count,
            "percentage": round(count / total * 100, 1),
        }
        for topic, count in topic_counts.most_common()
    ]
