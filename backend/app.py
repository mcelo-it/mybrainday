from pathlib import Path
from typing import List, Dict, Any
import os
import secrets

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from rag_utils import RAGSystem


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
    allow_headers=["Content-Type", "X-Rebuild-Token"],
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]


rag = RAGSystem(
    docs_path="docs",
    cache_dir="cache",
    embedding_model="text-embedding-3-small",
    chat_model="gpt-4.1-mini",
    max_files=20,
    max_chunks=5000,
    retrieval_top_k=8,
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
    return {"status": "ok"}


@app.get("/videos")
def get_videos() -> List[Dict[str, Any]]:
    videos = []

    for doc in rag.documents:
        meta = rag.parse_filename(doc["filename"])
        videos.append(
            {
                "id": doc["doc_id"],
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
        "module_number": meta["module_number"],
        "module_name": meta["module_name"],
        "video_number": meta["video_number"],
        "video_name": meta["video_name"],
        "filename": doc["filename"],
        "content_preview": doc["text"][:3000],
    }


@app.get("/sources")
def get_sources() -> List[Dict[str, Any]]:
    sources = []

    for chunk in rag.last_retrieved_chunks:
        sources.append(
            {
                "module_number": chunk.get("module_number", ""),
                "module_name": chunk.get("module_name", ""),
                "video_number": chunk.get("video_number", ""),
                "video_name": chunk.get("video_name", ""),
                "time_range": chunk.get("time_range", ""),
                "score": chunk.get("score", 0),
                "text_preview": chunk.get("text", "")[:300],
            }
        )

    return sources


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Nachricht darf nicht leer sein.")

    answer = rag.ask(message)

    sources = []
    for chunk in rag.last_retrieved_chunks:
        sources.append(
            {
                "module_number": chunk.get("module_number", ""),
                "module_name": chunk.get("module_name", ""),
                "video_number": chunk.get("video_number", ""),
                "video_name": chunk.get("video_name", ""),
                "time_range": chunk.get("time_range", ""),
                "score": chunk.get("score", 0),
                "text_preview": chunk.get("text", "")[:300],
            }
        )

    return ChatResponse(answer=answer, sources=sources)


@app.post("/rebuild")
def rebuild(x_rebuild_token: str | None = Header(default=None)) -> Dict[str, str]:
    rebuild_token = os.getenv("REBUILD_TOKEN")
    if not rebuild_token or not x_rebuild_token or not secrets.compare_digest(x_rebuild_token, rebuild_token):
        raise HTTPException(status_code=404, detail="Nicht verfügbar.")

    try:
        rag.load_documents()
        rag.build_chunks()
        rag.create_embeddings()
        rag.save_cache()
        return {"status": "ok", "message": "Lehrvideoquellen und Suchindex wurden neu aufgebaut."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neuaufbau fehlgeschlagen: {e}")
