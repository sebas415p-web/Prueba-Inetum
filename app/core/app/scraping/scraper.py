"""
Módulo de Web Scraping.
Patrón Strategy — BBVAScraper, MultiPageBBVAScraper, BBVAProductScraper
son estrategias intercambiables vía ScraperContext.
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.core.config import config
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ── URLs de productos BBVA Colombia conocidas ─────────────────
BBVA_PRODUCT_URLS = [
    "https://www.bbva.com.co/personas/productos/tarjetas/credito.html",
    "https://www.bbva.com.co/personas/productos/tarjetas/credito/visa.html",
    "https://www.bbva.com.co/personas/productos/tarjetas/credito/mastercard.html",
    "https://www.bbva.com.co/personas/productos/tarjetas/debito.html",
    "https://www.bbva.com.co/personas/productos/tarjetas/colombia-vive.html",
    "https://www.bbva.com.co/personas/productos/cuentas.html",
    "https://www.bbva.com.co/personas/productos/cuentas/ahorro.html",
    "https://www.bbva.com.co/personas/productos/cuentas/ahorro/digital.html",
    "https://www.bbva.com.co/personas/productos/cuentas/ahorro/nomina.html",
    "https://www.bbva.com.co/personas/productos/cuentas/corriente.html",
    "https://www.bbva.com.co/personas/productos/prestamos.html",
    "https://www.bbva.com.co/personas/productos/prestamos/vehiculo.html",
    "https://www.bbva.com.co/personas/productos/prestamos/vivienda.html",
    "https://www.bbva.com.co/personas/productos/prestamos/online.html",
    "https://www.bbva.com.co/personas/productos/prestamos/consumo.html",
    "https://www.bbva.com.co/personas/productos/prestamos/consumo/libranza.html",
    "https://www.bbva.com.co/personas/productos/inversion.html",
    "https://www.bbva.com.co/personas/productos/inversion/cdt.html",
    "https://www.bbva.com.co/personas/productos/inversion/cdt/online.html",
    "https://www.bbva.com.co/personas/productos/inversion/fondos.html",
    "https://www.bbva.com.co/personas/productos/seguros.html",
    "https://www.bbva.com.co/personas/productos/seguros/libres.html",
    "https://www.bbva.com.co/personas/productos/leasing.html",
    "https://www.bbva.com.co/personas/productos/divisas.html",
    "https://www.bbva.com.co/personas/productos/banca-personal.html",
    "https://www.bbva.com.co/personas/productos/premium.html",
    "https://www.bbva.com.co/personas/servicios-digitales.html",
    "https://www.bbva.com.co/personas/servicios-digitales/app-bbva.html",
    "https://www.bbva.com.co/personas/servicios-digitales/bre-b.html",
    "https://www.bbva.com.co/personas/atencion-al-cliente.html",
    "https://www.bbva.com.co/personas/bbva-contigo.html",
    "https://www.bbva.com.co/personas/informacion-practica/tasas-y-tarifas.html",
    "https://www.bbva.com.co/personas/productos/pensionados.html",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CO,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ─── Interfaz base ────────────────────────────────────────────

class ScrapingStrategy(ABC):
    @abstractmethod
    def scrape(self, url: str) -> str | None:
        pass


# ─── Estrategia 1: página única ───────────────────────────────

class BBVAScraper(ScrapingStrategy):
    """Scrapea una sola URL."""

    def scrape(self, url: str) -> str | None:
        content = self._fetch_text(url)
        if not content:
            return None
        self._save("data/raw/bbva_raw.html", content)
        self._save("data/clean/bbva_clean.txt", content)
        logger.info("Scraping exitoso: %d chars de %s", len(content), url)
        return content

    @staticmethod
    def _fetch_text(url: str) -> str | None:
        try:
            resp = requests.get(url, timeout=config.scrape_timeout, headers=HEADERS)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "noscript", "iframe"]):
                tag.decompose()
            elements = soup.find_all(["p", "h1", "h2", "h3", "h4", "li", "td", "th", "span", "div"])
            lines = []
            for el in elements:
                text = el.get_text(separator=" ", strip=True)
                if len(text) > 30:  # solo textos con contenido real
                    lines.append(text)
            return "\n".join(lines) if lines else None
        except Exception as e:
            logger.warning("Error scrapeando %s: %s", url, e)
            return None

    @staticmethod
    def _save(path: str, content: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


# ─── Estrategia 2: URLs de productos predefinidas ─────────────

class BBVAProductScraper(ScrapingStrategy):
    """
    Scrapea la lista predefinida de URLs de productos BBVA.
    Más confiable que el crawling ciego porque sabemos exactamente
    qué páginas tienen información útil.
    """

    def __init__(self):
        self._scraped: list[str] = []

    def scrape(self, url: str) -> str | None:
        all_texts: list[str] = []
        urls_to_scrape = BBVA_PRODUCT_URLS
        total = len(urls_to_scrape)

        logger.info("Iniciando scraping de %d URLs de productos BBVA", total)

        for i, page_url in enumerate(urls_to_scrape, 1):
            logger.info("[%d/%d] %s", i, total, page_url)
            text = BBVAScraper._fetch_text(page_url)
            if text:
                # Agregar título de sección para el chunker
                product_name = page_url.split("/")[-1].replace(".html", "").replace("-", " ").title()
                all_texts.append(f"### {product_name}\nFuente: {page_url}\n{text}")
                self._scraped.append(page_url)
            time.sleep(config.scrape_delay)

        if not all_texts:
            logger.error("Ninguna URL retornó contenido.")
            return None

        combined = "\n\n---\n\n".join(all_texts)
        BBVAScraper._save("data/raw/bbva_products_raw.txt", combined)
        BBVAScraper._save("data/clean/bbva_products_clean.txt", combined)
        logger.info(
            "Scraping completado: %d/%d páginas | %d chars totales",
            len(self._scraped), total, len(combined)
        )
        return combined


# ─── Estrategia 3: multi-página crawling ─────────────────────

class MultiPageBBVAScraper(ScrapingStrategy):
    """Crawlea el dominio recursivamente hasta SCRAPE_MAX_PAGES."""

    def __init__(self):
        self._visited: set[str] = set()

    def scrape(self, url: str) -> str | None:
        base_domain = urlparse(url).netloc
        all_text: list[str] = []
        queue: list[str] = [url]

        logger.info("Crawling multi-página. Dominio: %s | Límite: %d", base_domain, config.scrape_max_pages)

        while queue and len(self._visited) < config.scrape_max_pages:
            current = queue.pop(0)
            if current in self._visited:
                continue
            self._visited.add(current)
            logger.info("[%d/%d] %s", len(self._visited), config.scrape_max_pages, current)

            text, links = self._fetch_page(current)
            if text:
                all_text.append(f"### Fuente: {current}\n{text}")

            for link in links:
                if link not in self._visited and urlparse(link).netloc == base_domain:
                    queue.append(link)
            time.sleep(config.scrape_delay)

        combined = "\n\n".join(all_text)
        BBVAScraper._save("data/raw/bbva_multipage_raw.txt", "\n".join(self._visited))
        BBVAScraper._save("data/clean/bbva_multipage_clean.txt", combined)
        logger.info("Crawling finalizado. Páginas: %d | Chars: %d", len(self._visited), len(combined))
        return combined if combined else None

    def _fetch_page(self, url: str) -> tuple[str | None, list[str]]:
        try:
            resp = requests.get(url, timeout=config.scrape_timeout, headers=HEADERS)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "noscript"]):
                tag.decompose()
            elements = soup.find_all(["p", "h1", "h2", "h3", "h4", "li"])
            text = "\n".join(el.get_text(strip=True) for el in elements if len(el.get_text(strip=True)) > 20)
            links = [
                urljoin(url, a["href"])
                for a in soup.find_all("a", href=True)
                if not a["href"].startswith(("#", "mailto:", "tel:"))
            ]
            return text or None, links
        except Exception as e:
            logger.warning("No se pudo scrapear %s: %s", url, e)
            return None, []


# ─── Context ──────────────────────────────────────────────────

class ScraperContext:
    def __init__(self, strategy: ScrapingStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: ScrapingStrategy) -> None:
        self._strategy = strategy

    def execute_scraping(self, url: str) -> str | None:
        logger.info("Estrategia activa: %s", type(self._strategy).__name__)
        return self._strategy.scrape(url)
