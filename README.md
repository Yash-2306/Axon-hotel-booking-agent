# 🏨 StayAI — Multi-Agent Hotel Booking Assistant

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app.streamlit.app)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-orange.svg)](https://crewai.com)
[![Groq](https://img.shields.io/badge/Groq-Llama%204-green.svg)](https://console.groq.com)
[![Playwright](https://img.shields.io/badge/Playwright-Stealth%20Browser-purple.svg)](https://playwright.dev)

> **A fully autonomous multi-agent AI system that searches for hotels in real-time by browsing the live web — no APIs, no static datasets.**

---

## 🌟 What It Does

StayAI orchestrates **3 specialized AI agents** to handle your hotel search end-to-end:

| Agent | Role | Tools |
|-------|------|-------|
| 🧠 **Trip Planner** | Parses natural language requests, resolves dates, extracts structured requirements | Trip Parser Tool |
| 🌐 **Live Search Agent** | Generates Kayak search URLs and browses live results via stealth browser | Kayak URL Builder + Playwright Browser |
| 📊 **Deal Analyst** | Scores hotels on price-to-value ratio, ranks top picks, produces formatted report | LLM Reasoning |

## 🏗️ Architecture

```
User Query (Natural Language)
        │
        ▼
┌─────────────────────────────┐
│   🧠 Trip Planner Agent     │
│  Extracts: destination,     │
│  dates, budget, prefs       │
└──────────────┬──────────────┘
               │ Structured requirements
               ▼
┌─────────────────────────────┐
│  🌐 Live Search Agent       │
│  1. Build Kayak URL         │
│  2. Stealth Browser fetch   │
│  3. Extract hotel listings  │
└──────────────┬──────────────┘
               │ Raw hotel data
               ▼
┌─────────────────────────────┐
│  📊 Deal Analyst Agent      │
│  Score → Rank → Report      │
│  with booking links         │
└─────────────────────────────┘
               │
               ▼
    Formatted Markdown Report
     in Streamlit Chat UI
```

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/YOUR_USERNAME/hotel-booking-agent.git
cd hotel-booking-agent

pip install -r requirements.txt
playwright install chromium
```

### 2. Configure API Key
```bash
cp .env.example .env
# Edit .env and add your Groq API key (free at console.groq.com)
```

### 3. Run
```bash
streamlit run app.py
```

## 🌐 Live Demo
[https://your-app.streamlit.app](https://your-app.streamlit.app)

## 💬 Example Queries
- *"Find hotels in Paris for 2 adults, Dec 10–15, budget $150/night"*
- *"Best rated hotels in Tokyo for next weekend, 1 person"*
- *"Cheap hotels in NYC with a pool, Jan 5–8, 2 adults max $200"*

## 🛠️ Tech Stack
- **Orchestration:** CrewAI (multi-agent framework)
- **LLM:** Groq API — Llama 4 Scout (free, ultra-fast inference)
- **Browser Automation:** Playwright (stealth mode, bypasses basic bot detection)
- **UI:** Streamlit with custom CSS dark theme
- **Deployment:** Streamlit Community Cloud

## 📂 Project Structure
```
hotel-booking-agent/
├── app.py              # Main Streamlit app + CrewAI orchestration
├── browser.py          # Stealth Playwright browser tool
├── kayak.py            # Kayak URL generator tool
├── tools.py            # Trip requirements parser tool
├── requirements.txt    
├── .streamlit/
│   └── config.toml     # Streamlit server config
└── .env.example        # Environment variable template
```

## 📝 License
MIT
