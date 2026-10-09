from pathlib import Path
from typing import List, Dict, Any
import os
import secrets
from threading import Lock

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .rag_utils import RAGSystem
from .citations import subject_area
from .sessions import SessionStore, SessionNotFound, SessionCapacityExceeded


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = FastAPI(title="Lehrvideo Chatbot API")

# Das Frontend wird vom selben Host ausgeliefert. CORS bleibt für optionale
# externe Nutzung der API konfigurierbar.
allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Rebuild-Token", "X-Conversation-ID"],
)


class ChatRequest(BaseModel):
    message: str = Field(max_length=8000)
    include_diagnostics: bool = False
    include_evidence_debug: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    diagnostics: Dict[str, Any] | None = None


sessions = SessionStore(
    ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "3600")),
    max_sessions=int(os.getenv("MAX_SESSIONS", "500")),
)
rebuild_lock = Lock()

rag = RAGSystem(
    docs_path=str(BASE_DIR / "docs"),
    cache_dir=str(BASE_DIR / "cache"),
    embedding_model="text-embedding-3-small",
    chat_model="gpt-4.1-mini",
    max_files=None,
    max_chunks=None,
    retrieval_top_k=16 if os.getenv("RAG_RETRIEVAL_MODE", "hybrid") == "hybrid" else 8,
    retrieval_mode=os.getenv("RAG_RETRIEVAL_MODE", "hybrid"),
    min_similarity_score=0.30,
)


def initialize_rag() -> None:
    rag.load_documents()

    try:
        rag.load_cache()
    except FileNotFoundError:
        print("Kein gespeicherter Suchindex gefunden. Lehrvideoquellen werden vorbereitet...")
        rag.build_chunks()
        rag.create_embeddings()
        rag.save_cache()


@app.on_event("startup")
def startup_event() -> None:
    initialize_rag()


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/style.css", include_in_schema=False)
def frontend_css() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "style.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
def frontend_js() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "app.js", media_type="application/javascript")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "revision": os.getenv("RENDER_GIT_COMMIT", "unknown"),
            "retrieval_mode": rag.retrieval_mode, **rag.index_status}


@app.get("/videos")
def get_videos() -> List[Dict[str, Any]]:
    videos = []

    for doc in rag.documents:
        meta = rag.parse_filename(doc["filename"])
        videos.append(
            {
                "id": doc["doc_id"],
                **subject_area(meta["module_number"]),
                "module_number": meta["module_number"],
                "module_name": meta["module_name"],
                "video_number": meta["video_number"],
                "video_name": meta["video_name"],
                "filename": doc["filename"],
            }
        )

    return videos


@app.get("/videos/{video_id}")
def get_video(video_id: int) -> Dict[str, Any]:
    matches = [d for d in rag.documents if d["doc_id"] == video_id]
    if not matches:
        raise HTTPException(status_code=404, detail="Lehrvideo nicht gefunden.")

    doc = matches[0]
    meta = rag.parse_filename(doc["filename"])

    return {
        "id": doc["doc_id"],
        **subject_area(meta["module_number"]),
        "module_number": meta["module_number"],
        "module_name": meta["module_name"],
        "video_number": meta["video_number"],
        "video_name": meta["video_name"],
        "filename": doc["filename"],
        "content_preview": doc["text"][:3000],
    }


@app.get("/sources")
def get_sources(x_conversation_id: str | None = Header(default=None, max_length=128)) -> List[Dict[str, Any]]:
    if x_conversation_id is None:
        return []
    try:
        with sessions.transaction(x_conversation_id) as (_, state):
            return state.last_citations
    except SessionNotFound:
        raise HTTPException(status_code=404, detail="Sitzung abgelaufen oder unbekannt. Bitte starte einen neuen Chat.")


@app.post("/chat", response_model=ChatResponse, response_model_exclude_none=True)
def chat(payload: ChatRequest, x_conversation_id: str | None = Header(default=None, max_length=128)) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Nachricht darf nicht leer sein.")

    try:
        with sessions.transaction(x_conversation_id) as (token, state):
            worker = rag.for_conversation(state)
            state.diagnostics_enabled = payload.include_diagnostics
            state.evidence_debug_enabled = payload.include_diagnostics and payload.include_evidence_debug
            answer = worker.ask(message)
            return ChatResponse(
                conversation_id=token,
                answer=answer,
                citations=state.last_citations,
                sources=state.last_citations,
                diagnostics={"trace": state.last_trace, "metrics": state.last_metrics,
                             "turn_type": (state.turn_plan or {}).get("turn_type"),
                             "answer_type": state.last_answer_type}
                if payload.include_diagnostics else None,
            )
    except SessionNotFound:
        raise HTTPException(status_code=404, detail="Sitzung abgelaufen oder unbekannt. Bitte starte einen neuen Chat.")
    except SessionCapacityExceeded:
        raise HTTPException(status_code=503, detail="Zurzeit sind alle Chat-Sitzungen belegt. Bitte versuche es später erneut.")


@app.post("/rebuild")
def rebuild(x_rebuild_token: str | None = Header(default=None)) -> Dict[str, str]:
    global rag
    rebuild_token = os.getenv("REBUILD_TOKEN")
    if not rebuild_token or not x_rebuild_token or not secrets.compare_digest(x_rebuild_token, rebuild_token):
        raise HTTPException(status_code=404, detail="Nicht verfügbar.")

    try:
        with rebuild_lock:
            # Build a separate snapshot; in-flight turns keep a consistent old index.
            replacement = rag.for_conversation(type(rag.state)())
            replacement.load_documents()
            replacement.build_chunks()
            replacement.create_embeddings()
            replacement.save_cache()
            rag = replacement
        return {"status": "ok", "message": "Lehrvideoquellen und Suchindex wurden neu aufgebaut."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neuaufbau fehlgeschlagen: {e}")
