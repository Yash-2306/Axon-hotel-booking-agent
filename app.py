import os
import json
import datetime
import subprocess
import sys
import streamlit as st

# Auto-install Playwright browsers (needed on Streamlit Cloud)
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
from crewai import Crew, Process, Task, Agent, LLM
from dotenv import load_dotenv
from browser import stealth_browser
from kayak import kayak_hotels
from tools import parse_trip_requirements

load_dotenv()

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
    /* Main background */
    .stApp { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); }
    
    /* Header */
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

    /* Cards */
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

    /* Badges */
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

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: rgba(255,255,255,0.04) !important;
        border-right: 1px solid rgba(255,255,255,0.08);
    }
    
    /* Chat messages */
    .user-msg {
        background: linear-gradient(135deg, #FF385C22, #FF385C44);
        border: 1px solid #FF385C66;
        border-radius: 12px 12px 4px 12px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        color: white;
    }
    .agent-step {
        background: rgba(255,255,255,0.05);
        border-left: 3px solid #FF385C;
        padding: 0.5rem 1rem;
        margin: 0.25rem 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.85rem;
        color: #ccc;
    }
    
    /* Input overrides */
    .stTextInput > div > div > input { background: rgba(255,255,255,0.08) !important; color: white !important; border: 1px solid rgba(255,255,255,0.2) !important; }
    .stTextArea textarea { background: rgba(255,255,255,0.08) !important; color: white !important; border: 1px solid rgba(255,255,255,0.2) !important; }
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
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.markdown("---")

    # Load key from Streamlit secrets first (cloud), then let user override
    default_key = ""
    try:
        default_key = st.secrets.get("GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    except Exception:
        default_key = os.environ.get("GROQ_API_KEY", "")

    groq_key = st.text_input(
        "🔑 Groq API Key",
        type="password",
        value=default_key,
        help="Get a free key at console.groq.com"
    )
    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key
        st.cache_resource.clear()  # Force LLM rebuild with new key

    model_choice = st.selectbox(
        "🤖 Model",
        options=[
            "groq/llama-3.3-70b-versatile",
            "groq/llama-3.1-8b-instant",
        ],
        index=0,
        help="llama-3.3-70b-versatile is Groq's current flagship free model"
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
# LLM + AGENTS FACTORY
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_llm(model: str, api_key: str):
    return LLM(
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
    # Validate API key
    if not os.environ.get("GROQ_API_KEY"):
        st.error("⚠️ Please enter your Groq API key in the sidebar first.")
        st.stop()

    # Store user message
    st.session_state.messages.append({"role": "user", "content": query})
    st.markdown(f'<div class="user-msg">👤 {query}</div>', unsafe_allow_html=True)

    # Build and run crew
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    with st.status("🤖 AI Agents are working...", expanded=True) as status:
        st.write("🧠 **Trip Planner** — Parsing your request and extracting requirements...")
        st.write("🌐 **Search Agent** — Building Kayak URL and browsing live listings...")
        st.write("📊 **Deal Analyst** — Ranking hotels and computing value scores...")

        try:
            crew = build_crew(model_choice, groq_key)
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
                "- The Groq API key is invalid or rate-limited\n"
                "- Kayak blocked the browser request (common with cloud IPs)\n\n"
                "**Try:** A different destination, or check your API key in the sidebar."
            )

    # Display result
    st.markdown(response_text)
    st.session_state.messages.append({"role": "assistant", "content": response_text})

    # Add to search history
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
