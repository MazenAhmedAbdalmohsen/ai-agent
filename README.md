# 🤖 AI Agent

A production-ready AI Agent powered by **Claude** (Anthropic), with a clean chat UI and 6 built-in tools. Free to use.

---

## ✨ Features

| Tool | Description |
|------|-------------|
| 🔢 Calculator | Evaluate any math expression |
| 🌐 Web Search | Search via DuckDuckGo (no API key needed) |
| 🌤️ Weather | Current weather for any city (Open-Meteo, free) |
| 🕐 Date & Time | Current date and time |
| 📝 Notes | Save and read notes to disk |
| 📏 Unit Converter | Length, weight, temperature, speed |

---

## 🚀 Quick Start

### 1. Clone and enter the project

```bash
git clone <your-repo-url>
cd ai-agent
```

### 2. Create a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and set your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Get your key at:  https://console.groq.com

### 5. Run the server

```bash
# Option A: CLI
uvicorn main:app --reload

# Option B: Python
python main.py

# Option C: VS Code
# Press F5 (uses .vscode/launch.json)
```

### 6. Open in browser

```
http://localhost:8000
```

---

## 📁 Project Structure

```
ai-agent/
├── main.py              # FastAPI app & API routes
├── config.py            # Settings & environment variables
├── requirements.txt     # Python dependencies
├── .env.example         # Template for .env
├── .gitignore
│
├── agent/
│   ├── __init__.py
│   ├── agent.py         # Core agent loop (Claude + tool use)
│   ├── tools.py         # All tool definitions & handlers
│   └── memory.py        # Per-session conversation memory
│
├── frontend/
│   └── index.html       # Chat UI (served at /)
│
└── .vscode/
    ├── launch.json      # Debug config (F5 to run)
    └── extensions.json  # Recommended VS Code extensions
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Chat UI |
| `POST` | `/chat` | Send message to agent |
| `POST` | `/clear` | Clear session history |
| `GET` | `/history/{session_id}` | Get conversation history |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger API docs (auto-generated) |

### Example API call:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather in Cairo?", "session_id": "my-session"}'
```

---

## 🛠️ Add a New Tool

1. Define the tool schema in `agent/tools.py` (add to `TOOLS` list)
2. Write the handler function
3. Register it in `TOOL_HANDLERS` dict

That's it — the agent will automatically use it!

---

## ⚙️ Configuration

Edit `.env` to change behavior:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | **Required.** Your Anthropic API key |
| `MODEL` | `claude-opus-4-5` | Claude model to use |
| `MAX_TOKENS` | `4096` | Max tokens per response |
| `PORT` | `8000` | Server port |
| `SYSTEM_PROMPT` | *(see config.py)* | Custom system prompt |

---

## 🌐 Deploy (optional)

### Railway / Render / Fly.io

Just set `ANTHROPIC_API_KEY` as an environment variable and deploy. The app runs on port 8000.

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 📄 License

MIT — free to use, modify, and distribute.
