# BBVA RAG Conversational Assistant

Sistema **Retrieval-Augmented Generation (RAG)** que extrae información del sitio web de BBVA Colombia mediante Web Scraping y la expone a través de una interfaz conversacional con historial persistente, reranking semántico y analytics del uso.

---

## Índice

1. [Stack tecnológico](#stack-tecnológico)
2. [Arquitectura del sistema](#arquitectura-del-sistema)
3. [Patrones de diseño](#patrones-de-diseño)
4. [Requisitos previos](#requisitos-previos)
5. [Instalación y puesta en marcha](#instalación-y-puesta-en-marcha)
6. [Uso — CLI](#uso--cli-recomendado-para-demo)
7. [Uso — API REST](#uso--api-rest)
8. [Analytics](#analytics)
9. [Limitaciones y decisiones de diseño](#limitaciones-y-decisiones-de-diseño)
10. [Futuras mejoras](#futuras-mejoras)

---

## Stack tecnológico

| Componente | Tecnología | Justificación |
|---|---|---|
| **API** | FastAPI | Async nativo, esquemas Pydantic automáticos, OpenAPI gratis |
| **LLM** | Llama 3 vía **Groq** | Gratuito (~300 req/día), latencia <1 s, sin tarjeta de crédito |
| **Embeddings** | `all-MiniLM-L6-v2` (HuggingFace) | Open source, corre 100 % local, buena relación calidad/velocidad |
| **Reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Mejora precisión del contexto antes de pasarlo al LLM (BONUS) |
| **Vector Store** | **FAISS** | Self-hosted, sin costo, búsqueda ANN en milisegundos |
| **Historial** | **SQLite** | Sin dependencias externas, persistente, suficiente para demo |
| **Contenedor** | Docker + Docker Compose | Un solo comando levanta todo |
| **Scraping** | `requests` + `BeautifulSoup4` | Ligero; para SPAs complejas se usaría Playwright |

---

## Arquitectura del sistema

```
bbva_rag/
├── app/
│   ├── core/
│   │   ├── config.py          # Singleton — configuración centralizada
│   │   └── logging_config.py  # Logger con nivel configurable vía .env
│   ├── scraping/
│   │   └── scraper.py         # Strategy — BBVAScraper | MultiPageBBVAScraper
│   ├── processing/
│   │   └── processor.py       # Limpieza + chunking con overlap
│   ├── embeddings/
│   │   └── embedder.py        # Cache del modelo HuggingFace
│   ├── vector_store/
│   │   └── factory.py         # Factory — FAISS (extensible a Chroma/Qdrant)
│   ├── rag/
│   │   └── pipeline.py        # Recuperación → Reranking → LLM → Persistencia
│   ├── chat/
│   │   └── memory.py          # Repository — SQLite sin SQL en el dominio
│   ├── analytics/
│   │   └── analyzer.py        # Métricas, keywords, distribución temática
│   └── api/
│       └── main.py            # FastAPI — endpoints REST
├── chat_cli.py                # Interfaz CLI interactiva
├── Dockerfile                 # Multi-stage build, usuario non-root
├── docker-compose.yml         # Volumes persistentes por directorio
├── .env.example               # Plantilla de configuración
└── requirements.txt
```

### Flujo de datos

```
Usuario
  │
  ▼
[CLI / API]
  │
  ├─── POST /scrape ──► BBVAScraper / MultiPageBBVAScraper
  │                          │ HTML crudo → data/raw/
  │                          │ texto limpio → data/clean/
  │                          ▼
  │                     TextProcessor (clean + chunk)
  │                          ▼
  │                     VectorStoreFactory → FAISS → data/faiss_index/
  │
  └─── POST /chat ───► RAGPipeline
                            │
                       1. FAISS similarity_search (top-K)
                            │
                       2. CrossEncoder rerank (top-N)
                            │
                       3. ChatRepository.get_history(session_id)
                            │
                       4. Groq Llama 3 → respuesta
                            │
                       5. ChatRepository.add_message(...)
                            │
                        respuesta al usuario
```

---

## Patrones de diseño

### 1. Singleton — `ConfigManager` (`app/core/config.py`)

**Problema que resuelve:** evitar que múltiples módulos lean `os.getenv()` de forma independiente, lo que podría generar inconsistencias y carga innecesaria.

**Implementación:** se sobrescribe `__new__` para retornar siempre la misma instancia. `load_dotenv()` se ejecuta exactamente una vez.

```python
class ConfigManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            load_dotenv()
            cls._instance._load()
        return cls._instance
```

---

### 2. Strategy — `ScrapingStrategy` (`app/scraping/scraper.py`)

**Problema que resuelve:** distintos sitios requieren distintas estrategias de extracción (página única, multi-página, SPA con JS, etc.). El código cliente no debería cambiar al agregar una nueva estrategia.

**Implementación:** `ScrapingStrategy` define la interfaz (`scrape(url)`). `BBVAScraper` y `MultiPageBBVAScraper` son implementaciones concretas. `ScraperContext` inyecta la estrategia y puede cambiarla en runtime con `set_strategy()`.

```python
# Cambiar estrategia sin tocar el pipeline:
scraper = ScraperContext(BBVAScraper())
scraper.set_strategy(MultiPageBBVAScraper())  # basta esta línea
```

---

### 3. Factory — `VectorStoreFactory` (`app/vector_store/factory.py`)

**Problema que resuelve:** el resto del sistema no debería saber si el índice vectorial es FAISS, ChromaDB o Qdrant. La creación y carga del store se centraliza en un único lugar.

**Implementación:** método estático `get_vector_store(store_type, texts)`. Cambiar el motor = cambiar `VECTOR_DB_TYPE=chroma` en `.env`.

```python
# El RAGPipeline no sabe qué motor usa:
self.vector_store = VectorStoreFactory.get_vector_store()
```

---

### 4. Repository — `ChatRepository` (`app/chat/memory.py`)

**Problema que resuelve:** la lógica de negocio (RAGPipeline, AnalyticsModule) no debería contener SQL. Cambiar de SQLite a PostgreSQL no debería afectar al pipeline.

**Implementación:** `ChatRepository` expone `add_message()`, `get_history()`, `get_all_messages()` como métodos de dominio. Toda la interacción con SQLite está encapsulada. Un context manager interno garantiza rollback ante errores.

```python
# El pipeline solo habla con el repositorio:
self.repo.add_message(session_id, "user", query)
history = self.repo.get_history(session_id)
```

---

## Requisitos previos

- **Docker** ≥ 20.10 y **Docker Compose** ≥ 2.0
- **API Key de Groq** gratuita → [console.groq.com](https://console.groq.com) *(no requiere tarjeta de crédito)*
- Git
- Conexión a internet (para descargar modelos HuggingFace la primera vez, ~100 MB)

---

## Instalación y puesta en marcha

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/bbva_rag.git
cd bbva_rag
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Abre `.env` y reemplaza `tu_api_key_aqui` con tu Groq API Key. El resto de valores funciona con los defaults.

### 3. Crear directorios de datos

```bash
mkdir -p data/raw data/clean data/faiss_index data/db
```

### 4. Levantar el sistema

```bash
docker-compose up --build
```

La primera vez tarda ~3-5 minutos (descarga modelos HuggingFace). Las siguientes arrancas en ~30 segundos.

La API estará disponible en `http://localhost:8000`.
Documentación interactiva: `http://localhost:8000/docs`

### 5. Ejecutar el scraping e indexado (primer uso obligatorio)

```bash
# Scraping de la página principal (rápido, ~10 segundos)
curl -X POST http://localhost:8000/scrape

# Scraping multi-página (más contenido, ~2-5 minutos)
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"multi_page": true}'
```

---

## Uso — CLI (recomendado para demo)

```bash
# Dentro del contenedor
docker-compose run --rm rag_api python chat_cli.py

# O localmente (con virtualenv)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python chat_cli.py
```

**Comandos dentro de la CLI:**

| Comando | Acción |
|---|---|
| `scrape` | Scrapear página principal y construir índice |
| `scrape multi` | Crawling de múltiples páginas del dominio |
| `nueva` | Iniciar sesión con ID nuevo |
| `historial` | Ver mensajes de la sesión actual |
| `analytics` | Ver métricas del sistema en consola |
| `salir` | Cerrar la aplicación |

---

## Uso — API REST

### Chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "usuario_demo_01",
    "query": "¿Cuáles son los tipos de tarjetas de crédito que ofrece BBVA?"
  }'
```

### Ver historial de una sesión

```bash
curl http://localhost:8000/history/usuario_demo_01
```

### Listar todas las sesiones

```bash
curl http://localhost:8000/sessions
```

### Analytics

```bash
curl http://localhost:8000/analytics
```

### Health check

```bash
curl http://localhost:8000/health
```

---

## Analytics

El endpoint `/analytics` y el comando `analytics` en la CLI retornan:

```json
{
  "total_queries": 42,
  "total_responses": 42,
  "unique_sessions": 8,
  "avg_query_length_chars": 68.3,
  "avg_response_length_chars": 312.1,
  "avg_queries_per_session": 5.25,
  "most_active_session": { "session_id": "abc123", "query_count": 12 },
  "top_keywords": [
    { "keyword": "tarjeta", "count": 15 },
    { "keyword": "cuenta", "count": 11 }
  ],
  "topic_distribution": [
    { "topic": "Tarjetas de crédito", "count": 18, "percentage": 42.8 },
    { "topic": "Cuentas bancarias",   "count": 12, "percentage": 28.5 }
  ],
  "queries_last_7_days": [
    { "date": "2026-04-07", "queries": 5 },
    { "date": "2026-04-08", "queries": 11 }
  ],
  "activity_by_hour": [
    { "hour": "09:00", "queries": 8 },
    { "hour": "14:00", "queries": 14 }
  ]
}
```

---

## Limitaciones y decisiones de diseño

| Área | Limitación | Decisión tomada |
|---|---|---|
| **Scraping** | Sitios SPA (React/Angular) no renderizan con `requests` | Se usa BeautifulSoup; para SPAs agregar Playwright |
| **Vector Store** | FAISS no escala horizontalmente | Elegido por ser self-hosted y gratuito; migrar a Qdrant en producción |
| **Base de datos** | SQLite no soporta múltiples escritores concurrentes | Aceptable para demo; migrar a PostgreSQL + asyncpg en producción |
| **Autenticación** | La API no tiene auth | Agregar OAuth2 / API keys para exposición pública |
| **Modelos** | Modelos descargados en tiempo de build | Se podría pre-cachear en la imagen Docker para arranque más rápido |
| **Groq rate limit** | ~300 req/día en tier gratuito | Suficiente para demo; usar tier pagado o Ollama local para producción |

---

## Futuras mejoras

- **Interfaz Streamlit** para usuarios finales no técnicos
- **Scraping periódico** con Celery + Redis para mantener el índice actualizado
- **Evaluación RAG automática** con [RAGAS](https://docs.ragas.io) (faithfulness, answer relevancy, context precision)
- **Soporte multi-idioma** en embeddings con `paraphrase-multilingual-MiniLM-L12-v2`
- **Cache de respuestas** con Redis para queries frecuentes
- **Vector store cloud-native** (Qdrant / Pinecone) para escalabilidad horizontal
- **Autenticación JWT** + rate limiting por usuario
- **Orquestador de scraping** (Airflow / Prefect) con scheduling configurable
