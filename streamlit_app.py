"""
Interfaz Streamlit para el BBVA RAG Assistant.
Corre directamente contra la API FastAPI en localhost:8000.
"""
import uuid
import requests
import streamlit as st

API_URL = "http://rag_api:8000"   # nombre del servicio en docker-compose

# ── Configuración de página ───────────────────────────────────
st.set_page_config(
    page_title="BBVA RAG Assistant",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS personalizado ─────────────────────────────────────────
st.markdown("""
<style>
    /* Fondo general */
    .stApp { background-color: #f5f6fa; }

    /* Header BBVA azul */
    .bbva-header {
        background: linear-gradient(135deg, #004990 0%, #0066cc 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .bbva-header h1 { margin: 0; font-size: 1.8rem; }
    .bbva-header p  { margin: 0; opacity: 0.85; font-size: 0.95rem; }

    /* Burbuja usuario */
    .msg-user {
        background: #004990;
        color: white;
        padding: 0.8rem 1.2rem;
        border-radius: 18px 18px 4px 18px;
        margin: 0.5rem 0 0.5rem 15%;
        max-width: 85%;
        float: right;
        clear: both;
        font-size: 0.95rem;
    }
    /* Burbuja bot */
    .msg-bot {
        background: white;
        color: #1a1a2e;
        padding: 0.8rem 1.2rem;
        border-radius: 18px 18px 18px 4px;
        margin: 0.5rem 15% 0.5rem 0;
        max-width: 85%;
        float: left;
        clear: both;
        font-size: 0.95rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-left: 3px solid #004990;
    }
    .clearfix { clear: both; }

    /* Métricas */
    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        border-top: 3px solid #004990;
    }
    .metric-value { font-size: 2rem; font-weight: bold; color: #004990; }
    .metric-label { font-size: 0.8rem; color: #666; margin-top: 0.2rem; }

    /* Ocultar footer de Streamlit */
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Estado de sesión ──────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "rag_ready" not in st.session_state:
    st.session_state.rag_ready = False


# ── Helpers API ───────────────────────────────────────────────
def check_health() -> dict:
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        return r.json()
    except Exception:
        return {"status": "error", "rag_ready": False}


def run_scrape(mode: str = "products") -> dict:
    try:
        r = requests.post(
            f"{API_URL}/scrape",
            json={"mode": mode},
            timeout=300,
        )
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


def send_chat(session_id: str, query: str) -> str:
    try:
        r = requests.post(
            f"{API_URL}/chat",
            json={"session_id": session_id, "query": query},
            timeout=60,
        )
        data = r.json()
        if r.status_code == 200:
            return data.get("response", "Sin respuesta.")
        return f"Error {r.status_code}: {data.get('detail', 'Error desconocido')}"
    except requests.exceptions.Timeout:
        return "Timeout esperando respuesta. Intenta nuevamente."
    except Exception as e:
        return f"Error de conexión: {e}"


def get_analytics() -> dict:
    try:
        r = requests.get(f"{API_URL}/analytics", timeout=10)
        return r.json()
    except Exception:
        return {}


# ── Header ────────────────────────────────────────────────────
st.markdown("""
<div class="bbva-header">
    <div>
        <h1>🏦 BBVA RAG Assistant</h1>
        <p>Consulta información sobre productos y servicios de BBVA Colombia</p>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Panel de Control")

    # Estado del sistema
    health = check_health()
    rag_ready = health.get("rag_ready", False)
    st.session_state.rag_ready = rag_ready

    if health.get("status") == "ok":
        if rag_ready:
            st.success("✅ Sistema listo")
        else:
            st.warning("⚠️ Índice no inicializado")
    else:
        st.error("❌ API no disponible")

    st.divider()

    # Scraping
    st.markdown("### 🌐 Indexar contenido BBVA")
    scrape_mode = st.selectbox(
        "Modo de scraping",
        options=["products", "single", "multi"],
        format_func=lambda x: {
            "products": "📦 Productos (recomendado)",
            "single":   "📄 Página principal",
            "multi":    "🕷️ Multi-página",
        }[x],
    )

    if st.button("🚀 Ejecutar Scraping", use_container_width=True, type="primary"):
        with st.spinner("Scrapeando BBVA... esto puede tardar 2-3 min"):
            result = run_scrape(scrape_mode)
        if result.get("status") == "ok":
            st.success(
                f"✅ {result.get('chunks_generated', 0)} chunks generados\n\n"
                f"📄 {result.get('pages_scraped', 0)} páginas scrapeadas"
            )
            st.session_state.rag_ready = True
            st.rerun()
        else:
            st.error(f"❌ {result.get('message', result.get('detail', 'Error desconocido'))}")

    st.divider()

    # Sesión
    st.markdown("### 🔑 Sesión")
    st.code(f"{st.session_state.session_id[:8]}...", language=None)

    if st.button("🔄 Nueva sesión", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    if st.button("🗑️ Limpiar chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    # Config info
    cfg = health.get("config", {})
    if cfg:
        st.markdown("### 📋 Configuración")
        st.caption(f"**LLM:** {cfg.get('llm_model', '-')}")
        st.caption(f"**Embeddings:** {cfg.get('embedding_model', '-')}")
        st.caption(f"**Vector DB:** {cfg.get('vector_db', '-')}")
        st.caption(f"**Historial N:** {cfg.get('history_k', '-')} mensajes")


# ── Tabs principales ──────────────────────────────────────────
tab_chat, tab_analytics = st.tabs(["💬 Chat", "📊 Analytics"])


# ════════════════════════════════════════════════════════════
# TAB CHAT
# ════════════════════════════════════════════════════════════
with tab_chat:

    if not st.session_state.rag_ready:
        st.info(
            "👈 El índice no está inicializado. "
            "Ve al panel de control y ejecuta el **Scraping** primero."
        )

    # Mostrar historial de mensajes
    chat_container = st.container()
    with chat_container:
        if not st.session_state.messages:
            st.markdown("""
            <div style="text-align:center; padding: 3rem; color: #999;">
                <div style="font-size:3rem;">🏦</div>
                <div style="font-size:1.1rem; margin-top:1rem;">
                    ¡Hola! Soy el asistente virtual de BBVA Colombia.<br>
                    Pregúntame sobre productos, servicios, cuentas, tarjetas y más.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    st.markdown(
                        f'<div class="msg-user">👤 {msg["content"]}</div>'
                        '<div class="clearfix"></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="msg-bot">🏦 {msg["content"]}</div>'
                        '<div class="clearfix"></div>',
                        unsafe_allow_html=True,
                    )

    # Preguntas sugeridas
    if not st.session_state.messages:
        st.markdown("#### 💡 Preguntas frecuentes")
        cols = st.columns(2)
        suggestions = [
            "¿Qué tarjetas de crédito ofrece BBVA?",
            "¿Cómo abro una cuenta de ahorros?",
            "¿Qué tipos de préstamos tienen?",
            "¿Cuáles son los CDT disponibles?",
            "¿Cómo funciona la app BBVA?",
            "¿Qué seguros ofrece BBVA Colombia?",
        ]
        for i, suggestion in enumerate(suggestions):
            col = cols[i % 2]
            with col:
                if st.button(f"💬 {suggestion}", use_container_width=True, key=f"sugg_{i}"):
                    if st.session_state.rag_ready:
                        st.session_state.messages.append({"role": "user", "content": suggestion})
                        with st.spinner("🤔 Pensando..."):
                            response = send_chat(st.session_state.session_id, suggestion)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                        st.rerun()
                    else:
                        st.warning("Ejecuta el scraping primero.")

    # Input de chat
    st.markdown("---")
    with st.form("chat_form", clear_on_submit=True):
        col_input, col_btn = st.columns([5, 1])
        with col_input:
            user_input = st.text_input(
                "Escribe tu pregunta",
                placeholder="Ej: ¿Cuáles son los beneficios de la tarjeta Visa BBVA?",
                label_visibility="collapsed",
            )
        with col_btn:
            submitted = st.form_submit_button("Enviar ➤", use_container_width=True, type="primary")

    if submitted and user_input.strip():
        if not st.session_state.rag_ready:
            st.warning("⚠️ Ejecuta el scraping primero desde el panel lateral.")
        else:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.spinner("🤔 Pensando..."):
                response = send_chat(st.session_state.session_id, user_input)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()


# ════════════════════════════════════════════════════════════
# TAB ANALYTICS
# ════════════════════════════════════════════════════════════
with tab_analytics:
    st.markdown("### 📊 Métricas del sistema")

    if st.button("🔄 Actualizar métricas", type="primary"):
        st.rerun()

    metrics = get_analytics()

    if "message" in metrics:
        st.info(f"ℹ️ {metrics['message']}")
    elif "error" in metrics:
        st.error(f"Error: {metrics['error']}")
    elif metrics:
        # Métricas principales
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{metrics.get('total_queries', 0)}</div>
                <div class="metric-label">Total Consultas</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{metrics.get('unique_sessions', 0)}</div>
                <div class="metric-label">Sesiones Únicas</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{metrics.get('avg_queries_per_session', 0)}</div>
                <div class="metric-label">Queries / Sesión</div>
            </div>""", unsafe_allow_html=True)
        with c4:
            avg_len = metrics.get('avg_query_length_chars', 0)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{avg_len}</div>
                <div class="metric-label">Longitud Media (chars)</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")

        col_left, col_right = st.columns(2)

        # Keywords
        with col_left:
            st.markdown("#### 🔑 Keywords más frecuentes")
            keywords = metrics.get("top_keywords", [])
            if keywords:
                for kw in keywords[:10]:
                    pct = min(kw["count"] / keywords[0]["count"], 1.0)
                    st.markdown(f"**{kw['keyword']}** — {kw['count']} veces")
                    st.progress(pct)
            else:
                st.info("Sin datos aún.")

        # Temas
        with col_right:
            st.markdown("#### 🏷️ Distribución temática")
            topics = metrics.get("topic_distribution", [])
            if topics:
                for t in topics:
                    st.markdown(f"**{t['topic']}** — {t['percentage']}%")
                    st.progress(t["percentage"] / 100)
            else:
                st.info("Sin datos aún.")

        st.markdown("---")

        # Uso últimos 7 días
        st.markdown("#### 📅 Uso últimos 7 días")
        daily = metrics.get("queries_last_7_days", [])
        if daily:
            dates  = [d["date"] for d in daily]
            counts = [d["queries"] for d in daily]
            st.bar_chart(dict(zip(dates, counts)))
        else:
            st.info("Sin datos aún.")

        # Sesión más activa
        most_active = metrics.get("most_active_session", {})
        if most_active.get("session_id"):
            st.markdown("---")
            st.markdown(
                f"🏆 **Sesión más activa:** `{most_active['session_id'][:12]}...` "
                f"con **{most_active['query_count']}** consultas"
            )
    else:
        st.info("No hay conversaciones registradas aún. ¡Empieza a chatear!")
