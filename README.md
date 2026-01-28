# Fact-Check App – PDF Claim Extraction & Verification

A local-first, privacy-focused Streamlit web app that:

1. **Extracts** verifiable factual claims from PDF documents using LangChain + local Ollama LLM
2. **Verifies** those claims against the web using Tavily search + Ollama reasoning
3. **Generates** a human-readable fact-check report with verdicts, confidence scores, and recommendations

**Key features**
- Completely local LLM inference (via Ollama) – no cloud API keys required for extraction/verification
- Optional Tavily web search (free tier available)
- Beautiful, interactive Streamlit UI with progress bars, verdict cards, metrics, and downloadable reports
- No external pipeline scripts – everything runs through `app.py`

## Current Architecture (2026)
PDF upload
↓
LangChain + Ollama (local model e.g. mistral:latest or qwen2.5:14b)
↓ Extract verifiable claims (statistics, dates, financials, specs)
Tavily search (web evidence gathering)
↓
Ollama re-analyzes search results → assigns verdict (Verified / Inaccurate / False)
↓
FactCheckReporter generates summary + detailed report
↓
Interactive Streamlit UI + download (txt / json / html)
text## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running
  - Recommended models: `mistral:latest`, `qwen2.5:14b`, `llama3.2:3b`, `gemma2:27b`
  - Pull example: `ollama pull mistral:latest`
- Tavily API key (free tier: 1,000 credits on signup at https://app.tavily.com)

## Installation

1. Clone / open the project folder
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
(includes langchain, langchain-ollama, streamlit, pypdf, tavily-python, etc.)

(Optional) If you want to skip Tavily later, you can replace it with DuckDuckGo or SearxNG (see future notes).

Usage
1. Start Ollama (in a separate terminal)
Bashollama run mistral:latest
(or whichever model you pulled)
2. Start the Streamlit app
Bashpython -m streamlit run app.py
→ Opens in browser at http://localhost:8501
3. In the app

(Optional) Enter your Tavily API key in the sidebar if you want web verification
Get free key: https://app.tavily.com/home

Upload a PDF document
Adjust “Max claims to verify” slider (start with 3–5 to test quickly)
Click “Start Fact-Checking”

The app will:

Extract claims (Step 1/3)
Search the web and verify each claim (Step 2/3)
Generate an executive summary + detailed report (Step 3/3)

Output

Interactive dashboard with:
Document quality grade
Accuracy metrics
Verdict breakdown (Verified / Inaccurate / False)
High-priority issues list
Filterable detailed claim cards

Download buttons for:
Text report (.txt)
JSON report (.json)
HTML report (.html)


Example Workflow Screenshot (conceptual)

Upload quarterly report PDF
App extracts 17 claims (e.g. “Q1 2026 revenue growth -1.5%”, “February unemployment 6.2%”)
For each claim → Tavily search → Ollama evaluates evidence → verdict
Final report shows e.g. 70% verified, 2 high-priority issues flagged

Current Limitations & Notes

Speed: Local Ollama inference can be slow on laptops (15–60 seconds per claim on 14B model)
Verification quality: Depends heavily on the Ollama model and prompt. Mistral is decent; Qwen 2.5 or Gemma 2 are usually stronger.
Web search: Currently requires Tavily key. You can later replace it with DuckDuckGo (no key) or SearxNG.
Error handling: App now gracefully shows warnings when verification produces no results (e.g. Ollama not running, model not pulled, Tavily quota hit).

Project Structure
textFact-Checking Web App/
├── app.py                  # Main Streamlit application
├── claim_extractor.py      # PDF → claim extraction with LangChain + Ollama
├── claim_verifier.py       # Claim verification with Tavily search + Ollama
├── report_generator.py     # Report formatting & summary generation
├── search_providers.py     # Tavily-only search client
└── requirements.txt
Future Improvements (optional)

Replace Tavily with free DuckDuckGo or SearxNG search
Add retry logic for Ollama timeouts
Support batch PDF upload
Export results to CSV for spreadsheet analysis

Enjoy your local, private fact-checking tool!
Built with Streamlit, LangChain, Ollama & Tavily