from rag_utils import RAGSystem


def interactive_loop(rag: RAGSystem) -> None:
    print("\nLehrvideo-Chatbot gestartet.")
    print("Stelle eine fachliche Frage zu unseren Lehrvideos über PV-Anlagen.")
    print("Befehle:")
    print("  /hilfe         -> Hilfe anzeigen")
    print("  /lehrvideos    -> verfügbare Lehrvideos anzeigen")
    print("  /video <id>    -> eine hinterlegte Videoquelle anzeigen")
    print("  /quellen       -> zuletzt verwendete Quellenstellen anzeigen")
    print("  /neuaufbau     -> Videoquellen neu einlesen und Suchindex aktualisieren")
    print("  /exit          -> Beenden")

    while True:
        user_input = input("\nDu: ").strip()

        if not user_input:
            continue

        if user_input == "/exit":
            print("Chatbot beendet.")
            break

        elif user_input == "/hilfe":
            print("\nVerfuegbare Befehle:")
            print("  /lehrvideos")
            print("      Zeigt alle verfügbaren Lehrvideos an.")
            print("  /video <id>")
            print("      Zeigt eine hinterlegte Videoquelle an.")
            print("      Beispiel: /video 0")
            print("  /quellen")
            print("      Zeigt die zuletzt verwendeten Quellenstellen an.")
            print("  /neuaufbau")
            print("      Liest die Lehrvideoquellen neu ein und aktualisiert den Suchindex.")
            print("  /exit")
            print("      Beendet das Programm.")

        elif user_input == "/lehrvideos":
            rag.list_documents()

        elif user_input.startswith("/video "):
            try:
                doc_id = int(user_input.split()[1])
                rag.show_document(doc_id)
            except (IndexError, ValueError):
                print("Bitte eine gueltige Video-ID angeben. Beispiel: /video 0")

        elif user_input == "/quellen":
            rag.show_last_sources()

        elif user_input == "/neuaufbau":
            try:
                print("Lehrvideoquellen werden neu eingelesen und der Suchindex wird aktualisiert...")
                rag.load_documents()
                rag.build_chunks()
                rag.create_embeddings()
                rag.save_cache()
                print("Neuaufbau abgeschlossen.")
            except Exception as e:
                print(f"Fehler beim Neuaufbau: {e}")

        else:
            try:
                answer = rag.ask(user_input)
                print(f"\nBot: {answer}")
            except Exception as e:
                print(f"Fehler: {e}")


def main() -> None:
    rag = RAGSystem(
        docs_path="docs",
        cache_dir="cache",
        embedding_model="text-embedding-3-small",
        chat_model="gpt-4.1-mini",
        retrieval_top_k=8,
        min_similarity_score=0.30,
    )

    rag.load_documents()

    try:
        rag.load_cache()
    except FileNotFoundError:
        print("Kein gespeicherter Suchindex gefunden. Die Lehrvideoquellen werden jetzt vorbereitet...")
        rag.build_chunks()
        rag.create_embeddings()
        rag.save_cache()

    interactive_loop(rag)


if __name__ == "__main__":
    main()
