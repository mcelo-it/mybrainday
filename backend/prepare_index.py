"""Validate the committed search index and rebuild it only when required."""

from .index_manifest import CacheValidationError
from .rag_utils import RAGSystem


def ensure_index(rag: RAGSystem) -> str:
    """Keep a valid cache; rebuild only when source documents and cache differ."""
    rag.load_documents()

    try:
        rag.load_cache()
    except (FileNotFoundError, CacheValidationError) as error:
        print(f"Suchindex muss neu aufgebaut werden: {error}")
        rag.build_chunks()
        rag.create_embeddings()
        rag.save_cache()
        print("Suchindex wurde erfolgreich neu aufgebaut.")
        return "rebuilt"

    print("Suchindex ist aktuell; kein Neuaufbau erforderlich.")
    return "current"


def main() -> None:
    rag = RAGSystem(
        docs_path="docs",
        cache_dir="cache",
        embedding_model="text-embedding-3-small",
        chat_model="gpt-4.1-mini",
    )
    ensure_index(rag)


if __name__ == "__main__":
    main()
