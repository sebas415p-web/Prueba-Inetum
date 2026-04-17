"""
Módulo de procesamiento y chunking de texto.
Limpia el texto crudo y lo divide en fragmentos (chunks) con overlap
para preservar contexto en los límites entre chunks.
"""
import re

from app.core.config import config
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class TextProcessor:
    """Limpia texto HTML extraído y lo divide en chunks configurables."""

    # Caracteres que se usan como marcadores de sección en el scraper
    SECTION_MARKER = "### Fuente:"

    def clean(self, text: str) -> str:
        """
        Aplica limpieza progresiva:
        1. Colapsa líneas en blanco excesivas.
        2. Elimina espacios y tabulaciones múltiples.
        3. Elimina líneas de un solo carácter o puramente numéricas.
        4. Elimina URLs sueltas (no informativas como texto).
        """
        # Normalizar saltos de línea
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Colapsar 3+ saltos a 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Espacios múltiples → uno
        text = re.sub(r"[ \t]+", " ", text)
        # Eliminar líneas triviales (solo puntuación, números solos o muy cortas)
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if len(stripped) < 3:
                continue
            if re.fullmatch(r"[\d\s\.\-\|]+", stripped):
                continue
            lines.append(stripped)
        clean = "\n".join(lines)
        logger.debug("Texto limpiado: %d → %d chars", len(text), len(clean))
        return clean

    def chunk(self, text: str) -> list[str]:
        """
        Divide el texto en chunks de `config.chunk_size` palabras
        con un overlap del `config.chunk_overlap_ratio` para no perder
        contexto en los bordes de cada fragmento.

        Si el texto contiene marcadores de sección (multi-page scraper),
        respeta las fronteras de sección antes de aplicar el overlap.
        """
        size = config.chunk_size
        overlap = max(1, int(size * config.chunk_overlap_ratio))
        chunks: list[str] = []

        # Si hay secciones por fuente, chunkear por sección
        if self.SECTION_MARKER in text:
            sections = [s.strip() for s in text.split(self.SECTION_MARKER) if s.strip()]
            for section in sections:
                section_chunks = self._chunk_words(section, size, overlap)
                chunks.extend(section_chunks)
        else:
            chunks = self._chunk_words(text, size, overlap)

        logger.info(
            "Chunking completado: %d chunks (size=%d, overlap=%d)",
            len(chunks), size, overlap,
        )
        return chunks

    @staticmethod
    def _chunk_words(text: str, size: int, overlap: int) -> list[str]:
        words = text.split()
        result = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i: i + size])
            if chunk.strip():
                result.append(chunk)
            i += size - overlap
        return result
