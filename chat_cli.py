#!/usr/bin/env python3
"""
CLI conversacional del BBVA RAG Assistant.
Uso: python chat_cli.py
"""
import os
import sys
import uuid

# Garantiza que los módulos del proyecto estén en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.logging_config import setup_logging
setup_logging()

BANNER = """
╔══════════════════════════════════════════════════╗
║       BBVA RAG Assistant  ·  CLI v1.0            ║
╠══════════════════════════════════════════════════╣
║  Comandos especiales:                            ║
║    scrape        → scrapear y construir índice   ║
║    scrape multi  → crawling multi-página         ║
║    nueva         → iniciar sesión nueva          ║
║    historial     → ver historial de esta sesión  ║
║    analytics     → ver métricas del sistema      ║
║    salir         → cerrar la aplicación          ║
╚══════════════════════════════════════════════════╝
"""


def _run_scraping(multi: bool = False) -> bool:
    from app.core.config import config
    from app.processing.processor import TextProcessor
    from app.scraping.scraper import BBVAScraper, MultiPageBBVAScraper, ScraperContext
    from app.vector_store.factory import VectorStoreFactory

    strategy = MultiPageBBVAScraper() if multi else BBVAScraper()
    mode = "multi-página" if multi else "página única"
    print(f"\n🌐 Scrapeando {config.bbva_url} ({mode})...")
    scraper = ScraperContext(strategy)
    raw_text = scraper.execute_scraping(config.bbva_url)

    if not raw_text:
        print("❌ El scraping no retornó contenido. Verifica la URL o tu conexión.")
        return False

    print("🔧 Limpiando y chunkeando texto...")
    processor = TextProcessor()
    clean = processor.clean(raw_text)
    chunks = processor.chunk(clean)
    print(f"✅ {len(chunks)} chunks generados.")

    print("📦 Construyendo índice vectorial FAISS...")
    VectorStoreFactory.get_vector_store(texts=chunks)
    print("✅ Índice guardado.\n")
    return True


def _load_pipeline():
    from app.rag.pipeline import RAGPipeline
    return RAGPipeline()


def _show_analytics():
    from app.analytics.analyzer import AnalyticsModule
    metrics = AnalyticsModule().get_metrics()
    if "message" in metrics:
        print(f"📊 {metrics['message']}")
        return
    if "error" in metrics:
        print(f"❌ Error: {metrics['error']}")
        return

    print("\n📊 ── Analytics ──────────────────────────────")
    print(f"  Queries totales        : {metrics['total_queries']}")
    print(f"  Sesiones únicas        : {metrics['unique_sessions']}")
    print(f"  Avg. longitud query    : {metrics['avg_query_length_chars']} chars")
    print(f"  Avg. queries/sesión    : {metrics['avg_queries_per_session']}")
    print(f"  Sesión más activa      : {metrics['most_active_session']['session_id']} "
          f"({metrics['most_active_session']['query_count']} queries)")

    print("\n  Top keywords:")
    for kw in metrics.get("top_keywords", [])[:8]:
        bar = "█" * min(kw["count"], 20)
        print(f"    {kw['keyword']:20s} {bar} {kw['count']}")

    print("\n  Distribución temática:")
    for t in metrics.get("topic_distribution", []):
        print(f"    {t['topic']:30s} {t['percentage']}%  ({t['count']} queries)")

    print("\n  Uso últimos 7 días:")
    for d in metrics.get("queries_last_7_days", []):
        bar = "█" * min(d["queries"], 30)
        print(f"    {d['date']}  {bar or '·'}  {d['queries']}")
    print()


def main():
    print(BANNER)

    # Intentar cargar pipeline
    pipeline = None
    print("⏳ Inicializando sistema RAG...")
    try:
        pipeline = _load_pipeline()
        print("✅ Sistema listo.\n")
    except FileNotFoundError:
        print("⚠️  Índice vectorial no encontrado.")
        ans = input("   ¿Ejecutar scraping ahora? (s/n): ").strip().lower()
        if ans == "s":
            if _run_scraping():
                pipeline = _load_pipeline()
                print("✅ Sistema listo.\n")
            else:
                print("❌ No se pudo inicializar. Usa el comando 'scrape' para reintentar.")
        else:
            print("   Escribe 'scrape' cuando estés listo.\n")
    except ValueError as e:
        print(f"❌ Error de configuración: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    session_id = str(uuid.uuid4())
    print(f"🔑 Sesión activa: {session_id[:8]}...\n")

    while True:
        try:
            user_input = input("Tú: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 ¡Hasta luego!")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in ("salir", "exit", "quit"):
            print("👋 ¡Hasta luego!")
            break

        elif cmd == "nueva":
            session_id = str(uuid.uuid4())
            print(f"🔄 Nueva sesión: {session_id[:8]}...\n")

        elif cmd.startswith("scrape"):
            multi = "multi" in cmd
            if _run_scraping(multi=multi):
                try:
                    pipeline = _load_pipeline()
                    print("✅ Sistema actualizado.\n")
                except Exception as e:
                    print(f"❌ Error al recargar pipeline: {e}\n")

        elif cmd == "analytics":
            _show_analytics()

        elif cmd == "historial":
            from app.chat.memory import ChatRepository
            history = ChatRepository().get_history(session_id, k=100)
            if not history:
                print("   (Sin mensajes en esta sesión)\n")
            else:
                print(f"\n── Historial sesión {session_id[:8]} ──")
                for msg in history:
                    prefix = "Tú" if msg["role"] == "user" else "Bot"
                    print(f"  [{prefix}] {msg['content'][:120]}")
                print()

        else:
            if pipeline is None:
                print("⚠️  Sistema no inicializado. Escribe 'scrape' para comenzar.\n")
                continue
            print("🤔 Pensando...")
            try:
                resp = pipeline.generate_response(session_id, user_input)
                print(f"\n🤖 BBVA Bot: {resp}\n")
            except Exception as e:
                print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    main()
