from rag_utils import RAGSystem


def main():
    rag = RAGSystem(
        docs_path="docs",
        cache_dir="cache",
        embedding_model="text-embedding-3-small",
        chat_model="gpt-4.1-mini",
    )

    rag.load_documents()
    rag.build_chunks()
    rag.create_embeddings()
    rag.save_cache()

    print("\nIndexing abgeschlossen.")
    print("Du kannst jetzt chatbot.py starten.")


if __name__ == "__main__":
    main()
