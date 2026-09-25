import os
import sys
import datetime
import subprocess
import threading
import time
import urllib.request
import streamlit as st

# ──────────────────────────────────────────────────────────────────────────────
# GROQ API KEY — tries secrets (case-insensitive + nested tables), env vars,
# and provides an optional sidebar override so you are never locked out
# ──────────────────────────────────────────────────────────────────────────────
def _load_groq_key_from_secrets() -> tuple[str, list[str]]:
    detected_keys = []
    # Try traversing st.secrets dynamically
    try:
        for k in st.secrets.keys():
            detected_keys.append(str(k))
            val = st.secrets[k]
            if isinstance(val, dict):
                for sub_k, sub_v in val.items():
                    detected_keys.append(f"{k}.{sub_k}")
                    if "groq" in sub_k.lower() and "key" in sub_k.lower():
                        if str(sub_v).strip():
                            return str(sub_v).strip(), detected_keys
            elif "groq" in str(k).lower() and "key" in str(k).lower():
                if str(val).strip():
                    return str(val).strip(), detected_keys
    except Exception:
        pass

    # Try standard environment variable
    env_val = os.environ.get("GROQ_API_KEY", "").strip()
    if env_val:
        return env_val, detected_keys

    return "", detected_keys

_AUTO_KEY, _DETECTED_SECRETS_KEYS = _load_groq_key_from_secrets()

if _AUTO_KEY:
    os.environ["GROQ_API_KEY"] = _AUTO_KEY

# ──────────────────────────────────────────────────────────────────────────────
# AUTO-INSTALL PLAYWRIGHT (needed on Streamlit Cloud)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _install_playwright():
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
            check=False, capture_output=True, timeout=120
        )
    except Exception:
        pass

_install_playwright()

from langchain_groq import ChatGroq
from crewai import Crew, Process, Task, Agent
from browser import stealth_browser
from kayak import kayak_hotels
from tools import parse_trip_requirements

# ──────────────────────────────────────────────────────────────────────────────
# KEEP-ALIVE PING (prevents Streamlit Cloud from sleeping)
# ──────────────────────────────────────────────────────────────────────────────
_PING_URL = None  # Auto-detected from Streamlit's browser URL if available

def _ping_loop():
    """Pings this app's URL every 4 minutes to prevent Streamlit sleep."""
    while True:
        time.sleep(240)
        try:
            url = st.session_state.get("_app_url")
            if url:
                urllib.request.urlopen(url, timeout=10)
        except Exception:
            pass

# Start ping thread once per session (daemon so it dies with the process)
if "ping_started" not in st.session_state:
    st.session_state["ping_started"] = True
    t = threading.Thread(target=_ping_loop, daemon=True)
    t.start()

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="StayAI – Smart Hotel Finder",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); }

    .main-header {
        background: linear-gradient(90deg, #FF385C, #FF7B8A);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 900;
        text-align: center;
        padding: 1rem 0 0.25rem;
        letter-spacing: -1px;
    }
    .sub-header {
        text-align: center;
        color: #aaa;
        font-size: 1rem;
        margin-bottom: 2rem;
    }

    .hotel-card {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
        backdrop-filter: blur(12px);
        transition: transform 0.2s;
    }
    .hotel-card:hover { transform: translateY(-2px); }

    .badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        margin: 0.2rem;
    }
    .badge-deal  { background: #FF385C; color: white; }
    .badge-rated { background: #00b894; color: white; }
    .badge-tag   { background: rgba(255,255,255,0.15); color: #eee; }

    section[data-testid="stSidebar"] {
        background: rgba(255,255,255,0.04) !important;
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    .user-msg {
        background: linear-gradient(135deg, #FF385C22, #FF385C44);
        border: 1px solid #FF385C66;
        border-radius: 12px 12px 4px 12px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        color: white;
    }

    .stTextArea textarea {
        background: rgba(255,255,255,0.08) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🏨 StayAI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Multi-Agent Hotel Search · Powered by CrewAI + Groq + Live Browser</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────────────────────
_ACTIVE_KEY = _AUTO_KEY
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.markdown("---")

    # Determine effective key
    user_entered = st.session_state.get("user_key", "").strip()

    if _AUTO_KEY:
        masked = _AUTO_KEY[:8] + "..." + _AUTO_KEY[-4:]
        st.success(f"✅ Key active from secrets ({masked})")
        effective_key = _AUTO_KEY
    elif user_entered:
        masked = user_entered[:8] + "..." + user_entered[-4:]
        st.success(f"✅ Key active ({masked})")
        effective_key = user_entered
        if st.button("Change Key", key="reset_key_btn"):
            st.session_state["user_key"] = ""
            st.rerun()
    else:
        st.info("🔑 Enter your Groq API Key to start:")
        manual_key = st.text_input(
            "Groq API Key",
            type="password",
            placeholder="gsk_...",
            help="Free key from console.groq.com",
            key="input_groq_key"
        )
        if manual_key:
            st.session_state["user_key"] = manual_key.strip()
            st.rerun()
        effective_key = manual_key.strip() if manual_key else ""

    _ACTIVE_KEY = effective_key
    if _ACTIVE_KEY:
        os.environ["GROQ_API_KEY"] = _ACTIVE_KEY

    model_choice = st.selectbox(
        "🤖 Model",
        options=[
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
        ],
        index=0,
        help="llama-3.3-70b-versatile is Groq's current flagship free model",
    )

    st.markdown("---")
    st.markdown("### 📖 How It Works")
    st.markdown("""
**3 Specialized AI Agents:**

🧠 **Trip Planner**  
Understands your request & extracts travel requirements

🌐 **Live Search Agent**  
Browses Kayak in real-time to find available hotels

📊 **Deal Analyst**  
Scores & ranks hotels by value, ratings and your preferences
""")

    st.markdown("---")
    st.markdown("### 💡 Example Queries")
    examples = [
        "Find hotels in Paris for 2 adults, Dec 10-15, budget $150/night",
        "Best rated hotels in Tokyo for 1 person next weekend",
        "Cheap hotels in NYC with pool, Jan 5-8, 2 adults",
    ]
    for ex in examples:
        if st.button(f"📝 {ex[:40]}...", key=ex, use_container_width=True):
            st.session_state["prefill_query"] = ex

# ──────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "search_history" not in st.session_state:
    st.session_state.search_history = []

# ──────────────────────────────────────────────────────────────────────────────
# LLM + CREW FACTORY  (using langchain-groq directly — no litellm routing)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_llm(model: str, api_key: str):
    """Build a ChatGroq LLM — langchain-groq talks to Groq natively."""
    return ChatGroq(
        model=model,
        api_key=api_key,
        temperature=0.3,
    )


def build_crew(model: str, api_key: str) -> Crew:
    llm = get_llm(model, api_key)

    # ── Agent 1: Trip Requirements Planner ──────────────────────────────────
    planner = Agent(
        role="Expert Travel Planner",
        goal=(
            "Parse user hotel search requests and extract precise, structured trip "
            "requirements including destination, dates, guest count, budget, and preferences."
        ),
        backstory=(
            "You are a seasoned travel concierge with 20 years of experience at luxury agencies. "
            "You are meticulous about extracting every detail from guest requests to ensure "
            "the search team finds exactly the right property. You always confirm dates are valid "
            "and resolve relative date references (e.g. 'next weekend', 'next month') to actual dates."
        ),
        tools=[parse_trip_requirements],
        llm=llm,
        verbose=True,
        memory=False,
    )

    # ── Agent 2: Live Hotel Search Agent ────────────────────────────────────
    searcher = Agent(
        role="Live Hotel Search Specialist",
        goal=(
            "Search Kayak for real hotel listings based on the trip requirements, "
            "browse the live results, and extract a clean list of available hotels with "
            "names, prices, ratings, and amenities."
        ),
        backstory=(
            "You are a data-driven hotel researcher who lives on travel aggregator sites. "
            "You know exactly how to navigate Kayak search results, spot the best deals, "
            "and extract clean structured data from noisy HTML. You always use the Kayak URL "
            "generator tool first to build the search URL, then use the Stealth Web Browser "
            "to retrieve live listings. If the browser fails, you fall back to generating "
            "a recommended search URL and explaining what the user should expect to find."
        ),
        tools=[kayak_hotels, stealth_browser],
        llm=llm,
        verbose=True,
        memory=False,
    )

    # ── Agent 3: Deal Analyst ────────────────────────────────────────────────
    analyst = Agent(
        role="Hotel Value & Deal Analyst",
        goal=(
            "Analyze the hotel results and produce a beautifully formatted, ranked "
            "recommendation report with deal scores, value analysis, and direct booking links."
        ),
        backstory=(
            "You are a hospitality economist who has analyzed thousands of hotel listings. "
            "You score hotels on a composite value index (price-to-rating ratio, included amenities, "
            "cancellation policy, location quality). You always present your analysis in clean "
            "markdown with emojis and tables, and you highlight the #1 recommended stay. "
            "You MUST always include the Kayak booking URL for each hotel you recommend."
        ),
        tools=[],
        llm=llm,
        verbose=True,
        memory=False,
    )

    # ── Tasks ────────────────────────────────────────────────────────────────
    task_plan = Task(
        description=(
            "Parse the following hotel search request and extract structured trip requirements:\n\n"
            "USER REQUEST: {user_request}\n\n"
            "Today's date: {today_date}\n\n"
            "Extract: destination, check_in_date, check_out_date, num_adults, "
            "max_budget_per_night, hotel_preferences, special_notes. "
            "Resolve any relative dates to actual YYYY-MM-DD format."
        ),
        expected_output=(
            "A structured summary of trip requirements including exact dates, destination, "
            "guest count, and any budget or preference constraints."
        ),
        agent=planner,
    )

    task_search = Task(
        description=(
            "Using the trip requirements from the planner:\n"
            "1. Use the Kayak Hotel URL Generator tool to build the search URL\n"
            "2. Use the Stealth Web Browser to load that URL and get live hotel listings\n"
            "3. Extract hotel names, nightly prices, star ratings, key amenities, and any fees\n"
            "4. Return a clean structured list of at least 5 hotels found (or as many as available)\n"
            "5. If the browser returns an error or CAPTCHA block, still return the Kayak search URL "
            "and describe typical hotels for that market."
        ),
        expected_output=(
            "A structured list of hotel options with name, price per night, rating, "
            "amenities, and the Kayak URL to book each."
        ),
        agent=searcher,
        context=[task_plan],
    )

    task_analyze = Task(
        description=(
            "Analyze the hotel search results and create a professional recommendation report:\n"
            "1. Score each hotel on: price value (40%), guest rating (30%), amenity match (20%), "
            "cancellation flexibility (10%)\n"
            "2. Rank the top 5 hotels\n"
            "3. Format a clean markdown report with:\n"
            "   - A quick summary of the search\n"
            "   - A ranked table of top hotels\n"
            "   - Detailed card for each top-3 pick (with pros/cons)\n"
            "   - 🏆 #1 Best Value recommendation with reasoning\n"
            "   - Direct Kayak booking links\n"
            "4. Add a brief 'Money-Saving Tip' section specific to this destination"
        ),
        expected_output=(
            "A beautifully formatted markdown hotel recommendation report with ranked picks, "
            "value scores, pros/cons, and direct booking links."
        ),
        agent=analyst,
        context=[task_plan, task_search],
    )

    return Crew(
        agents=[planner, searcher, analyst],
        tasks=[task_plan, task_search, task_analyze],
        process=Process.sequential,
        verbose=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# MAIN CHAT INTERFACE
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("---")

# Display chat history
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f'<div class="user-msg">👤 {msg["content"]}</div>', unsafe_allow_html=True)
    else:
        with st.container():
            st.markdown(msg["content"])

# Input box
prefill = st.session_state.pop("prefill_query", "")
query = st.chat_input(
    placeholder="e.g. 'Find hotels in Paris for 2 adults, Dec 10-15, budget $150/night'",
)
if prefill and not query:
    query = prefill

if query:
    # Check key is available
    if not _ACTIVE_KEY:
        st.error("❌ Groq API key is required. Please add it to Streamlit secrets or enter it in the sidebar.")
        st.stop()

    # Store user message
    st.session_state.messages.append({"role": "user", "content": query})
    st.markdown(f'<div class="user-msg">👤 {query}</div>', unsafe_allow_html=True)

    today = datetime.datetime.now().strftime("%Y-%m-%d")

    with st.status("🤖 AI Agents are working...", expanded=True) as status:
        st.write("🧠 **Trip Planner** — Parsing your request and extracting requirements...")
        st.write("🌐 **Search Agent** — Building Kayak URL and browsing live listings...")
        st.write("📊 **Deal Analyst** — Ranking hotels and computing value scores...")

        try:
            crew = build_crew(model_choice, _ACTIVE_KEY)
            result = crew.kickoff(inputs={
                "user_request": query,
                "today_date": today,
            })
            status.update(label="✅ Search complete!", state="complete", expanded=False)
            response_text = str(result)
        except Exception as e:
            status.update(label="⚠️ Search encountered an issue", state="error", expanded=False)
            response_text = (
                f"⚠️ **Search Error:** {str(e)}\n\n"
                "This usually happens when:\n"
                "- Kayak blocked the browser request (common with cloud IPs)\n"
                "- Groq rate limit reached (wait 60s and retry)\n\n"
                "**Try:** A different destination or a simpler query."
            )

    st.markdown(response_text)
    st.session_state.messages.append({"role": "assistant", "content": response_text})

    st.session_state.search_history.append({
        "query": query,
        "timestamp": datetime.datetime.now().strftime("%H:%M"),
    })

# Search history in sidebar
if st.session_state.search_history:
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🕐 Recent Searches")
        for item in reversed(st.session_state.search_history[-5:]):
            st.caption(f"⏰ {item['timestamp']} — {item['query'][:45]}...")
