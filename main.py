"""
AI Agent - Main FastAPI Application
Run with: uvicorn main:app --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
import os

from agent.agent import AIAgent
from agent.memory import ConversationMemory
from config import settings

app = FastAPI(
    title="AI Agent API",
    description="A powerful AI Agent with PC control capabilities",
    version="1.0.0"
)

# Allow all origins for dev (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for frontend assets
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# In-memory session store  {session_id: ConversationMemory}
sessions: dict[str, ConversationMemory] = {}


# ── Startup event ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    print(f"🤖 AI Agent Server Started — model: {settings.MODEL}")


# ── Pydantic models ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tool_calls: list[dict] = []

class ClearRequest(BaseModel):
    session_id: Optional[str] = "default"


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Serve the chat UI"""
    possible_paths = [
        "frontend/index.html",
        "static/index.html",
        "index.html",
        os.path.join(os.path.dirname(__file__), "index.html"),
        os.path.join(os.path.dirname(__file__), "frontend/index.html"),
        os.path.join(os.path.dirname(__file__), "static/index.html"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path)

    return {
        "status": "API Running",
        "message": "Frontend not found. Please ensure index.html is in the project root, frontend/, or static/ directory.",
        "endpoints": ["/chat", "/clear", "/history/{session_id}", "/health"]
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the AI agent and get a response"""
    session_id = request.session_id or "default"

    # Debug logging for incoming requests
    print(f"[/chat] session={session_id!r} message={request.message[:120]!r}")

    # Get or create session memory
    if session_id not in sessions:
        sessions[session_id] = ConversationMemory()

    memory = sessions[session_id]

    try:
        agent = AIAgent(memory=memory)
        reply, tool_calls = await agent.run(request.message)

        return ChatResponse(
            reply=reply,
            session_id=session_id,
            tool_calls=tool_calls
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clear")
async def clear_session(request: ClearRequest):
    """Clear conversation history for a session"""
    session_id = request.session_id or "default"
    if session_id in sessions:
        sessions[session_id].clear()
    return {"message": f"Session '{session_id}' cleared.", "session_id": session_id}


@app.get("/history/{session_id}")
async def get_history(session_id: str):
    """Get conversation history for a session"""
    if session_id not in sessions:
        return {"messages": []}
    return {"messages": sessions[session_id].get_messages()}


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "AI Agent v1.0"}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)