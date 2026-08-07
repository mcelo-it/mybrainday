import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class RAGSystem:
    def __init__(
        self,
        docs_path: str = "docs",
        cache_dir: str = "cache",
        embedding_model: str = "text-embedding-3-small",
        chat_model: str = "gpt-4.1-mini",
        #Hier die Limits anpassen:
        max_files: Optional[int] = None,
        max_chunks: Optional[int] = None,
        retrieval_top_k: int = 8,
        min_similarity_score: float = 0.30,
    ):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        backend_dir = Path(__file__).resolve().parent
        repo_root = backend_dir.parent

        docs_path_from_env = os.getenv("RAG_DOCS_PATH")
        cache_dir_from_env = os.getenv("RAG_CACHE_DIR")

        self.docs_path = self._resolve_path(
            docs_path_from_env or docs_path,
            base_dir=backend_dir,
        )

        self.cache_dir = self._resolve_path(
            cache_dir_from_env or cache_dir,
            base_dir=backend_dir,
        )
        self.embedding_model = embedding_model
        self.chat_model = chat_model
        self.max_files = max_files
        self.max_chunks = max_chunks
        self.retrieval_top_k = retrieval_top_k
        self.min_similarity_score = min_similarity_score

        self.documents: List[Dict[str, Any]] = []
        self.chunks: List[Dict[str, Any]] = []
        self.embeddings: np.ndarray = np.array([])
        self.chat_history: List[Dict[str, str]] = []
        self.last_retrieved_chunks: List[Dict[str, Any]] = []

        self.pending_clarification: Optional[Dict[str, Any]] = None
        self.last_user_query: Optional[str] = None
        self.last_effective_query: Optional[str] = None
        self.last_answer_type: Optional[str] = None
        self.last_selected_chunks: List[Dict[str, Any]] = []
        self.last_topic_summary: Optional[str] = None

        self.chunks_file = self.cache_dir / "chunks.json"
        self.embeddings_file = self.cache_dir / "embeddings.npy"
        self.meta_file = self.cache_dir / "meta.json"

    def load_documents(self) -> None:
        if not self.docs_path.exists():
            raise FileNotFoundError(f"Ordner nicht gefunden: {self.docs_path}")

        txt_files = sorted(self.docs_path.glob("*.txt"))

        if self.max_files is not None:
            txt_files = txt_files[: self.max_files]

        if not txt_files:
            raise ValueError(f"Keine .txt-Dateien gefunden in: {self.docs_path}")

        self.documents = []

        for file_path in txt_files:
            text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
            if text:
                self.documents.append(
                    {
                        "doc_id": len(self.documents),
                        "filename": file_path.name,
                        "path": str(file_path),
                        "text": text,
                    }
                )

        print(f"{len(self.documents)} Lehrvideo-Quellen geladen.")

    @staticmethod
    def parse_filename(filename: str) -> Dict[str, str]:
        """
        Erwartetes Format:
        '01 Stringdesign 2 Elektrische Kenngroessen.txt'
        """
        stem = Path(filename).stem.strip()
        match = re.match(r"^(\d+)\s+(.*?)\s+(\d+)\s+(.*)$", stem)

        if not match:
            return {
                "module_number": "",
                "module_name": "",
                "video_number": "",
                "video_name": stem,
            }

        return {
            "module_number": match.group(1).strip(),
            "module_name": match.group(2).strip(),
            "video_number": match.group(3).strip(),
            "video_name": match.group(4).strip(),
        }

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def split_into_timestamp_segments(self, text: str) -> List[Dict[str, str]]:
        """
        Zerlegt den Text anhand von Zeitmarken wie:
        (0:00:36 - 0:00:58)
        """
        time_pattern = r"(\(\d{1,2}:\d{2}:\d{2}\s*-\s*\d{1,2}:\d{2}:\d{2}\))"
        parts = re.split(time_pattern, text)

        segments: List[Dict[str, str]] = []
        current_time: Optional[str] = None

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if re.fullmatch(time_pattern, part):
                current_time = part
            else:
                if current_time:
                    cleaned_text = part.strip()
                    if cleaned_text:
                        segments.append(
                            {
                                "time_range": current_time,
                                "text": cleaned_text,
                            }
                        )

        return segments

    def build_chunks(self) -> None:
        self.chunks = []

        for doc in self.documents:
            meta = self.parse_filename(doc["filename"])
            segments = self.split_into_timestamp_segments(doc["text"])

            for i, seg in enumerate(segments):
                if self.max_chunks is not None and len(self.chunks) >= self.max_chunks:
                    print(f"Maximale Anzahl an Videoausschnitten erreicht: {self.max_chunks}")
                    print(f"{len(self.chunks)} Videoausschnitte erstellt.")
                    return

                self.chunks.append(
                    {
                        "chunk_id": len(self.chunks),
                        "doc_id": doc["doc_id"],
                        "filename": doc["filename"],
                        "chunk_index": i,
                        "module_number": meta["module_number"],
                        "module_name": meta["module_name"],
                        "video_number": meta["video_number"],
                        "video_name": meta["video_name"],
                        "time_range": seg["time_range"],
                        "text": seg["text"],
                    }
                )

        print(f"{len(self.chunks)} Videoausschnitte erstellt.")

    def create_embeddings(self, batch_size: int = 100) -> None:
        if not self.chunks:
            raise ValueError("Keine Videoausschnitte vorhanden. Bitte zuerst build_chunks() aufrufen.")

        vectors = []
        total = len(self.chunks)

        for start in range(0, total, batch_size):
            batch = self.chunks[start : start + batch_size]
            texts = [chunk["text"] for chunk in batch]

            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=texts,
            )

            # Reihenfolge absichern: Ergebnisse nach Index sortieren
            for item in sorted(response.data, key=lambda d: d.index):
                vectors.append(item.embedding)

            print(f"Inhalte verarbeitet: {min(start + batch_size, total)}/{total}")

        self.embeddings = np.array(vectors, dtype=np.float32)
        print("Inhaltsindex erfolgreich erstellt.")


    def save_cache(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        with open(self.chunks_file, "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=2)

        np.save(self.embeddings_file, self.embeddings)

        meta = {
            "embedding_model": self.embedding_model,
            "chat_model": self.chat_model,
            "max_files": self.max_files,
            "max_chunks": self.max_chunks,
            "retrieval_top_k": self.retrieval_top_k,
            "min_similarity_score": self.min_similarity_score,
            "num_documents": len(self.documents),
            "num_chunks": len(self.chunks),
            "chunking_strategy": "timestamp_segments",
        }

        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        print(f"Index gespeichert in: {self.cache_dir}")

    def load_cache(self) -> None:
        if not self.chunks_file.exists():
            raise FileNotFoundError(f"Cache-Datei fehlt: {self.chunks_file}")

        if not self.embeddings_file.exists():
            raise FileNotFoundError(f"Cache-Datei fehlt: {self.embeddings_file}")

        with open(self.chunks_file, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)

        self.embeddings = np.load(self.embeddings_file)

        print(f"Index geladen aus: {self.cache_dir}")
        print(f"{len(self.chunks)} Videoausschnitte stehen bereit.")

    @staticmethod
    def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        denom = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
        if denom == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / denom)

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        if self.embeddings.size == 0:
            raise ValueError("Der Inhaltsindex fehlt. Bitte zuerst den Index laden.")

        if top_k is None:
            top_k = self.retrieval_top_k

        query_response = self.client.embeddings.create(
            model=self.embedding_model,
            input=query,
        )
        query_vector = np.array(query_response.data[0].embedding, dtype=np.float32)

        scores = []
        for i, chunk_vector in enumerate(self.embeddings):
            score = self.cosine_similarity(query_vector, chunk_vector)
            scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in scores[:top_k]:
            chunk = self.chunks[idx].copy()
            chunk["score"] = round(score, 4)
            results.append(chunk)

        self.last_retrieved_chunks = results
        return results

    @staticmethod
    def _resolve_path(path_value: str, base_dir: Path) -> Path:
        path = Path(path_value).expanduser()

        if path.is_absolute():
            return path.resolve()

        return (base_dir / path).resolve()

    def build_selection_context(self, retrieved_chunks: List[Dict[str, Any]]) -> str:
        context_parts = []

        for i, chunk in enumerate(retrieved_chunks, start=1):
            context_parts.append(
                f"[Quelle {i}]\n"
                f"Modulnummer: {chunk['module_number']}\n"
                f"Modulname: {chunk['module_name']}\n"
                f"Videonummer: {chunk['video_number']}\n"
                f"Videoname: {chunk['video_name']}\n"
                f"Dateiname: {chunk['filename']}\n"
                f"Zeitangabe: {chunk['time_range']}\n"
                f"Score: {chunk['score']}\n"
                f"Text: {chunk['text']}"
            )

        return "\n\n".join(context_parts)

    def is_smalltalk(self, user_query: str) -> bool:
        text = self.normalize_whitespace(user_query)

        if not text:
            return True

        system_prompt = (
            "Du klassifizierst Nutzereingaben fuer einen RAG-Chatbot zu Lehrvideos ueber PV-Anlagen. "
            "Gib ausschliesslich valides JSON zurueck im Format: "
            "{\"is_smalltalk\": true oder false}. "
            "is_smalltalk ist true bei Begruessung, Verabschiedung, Dank, kurzer Zustimmung, "
            "Hoeflichkeit, rein sozialer Reaktion oder Feedback ohne fachliche Frage. "
            "is_smalltalk ist false, wenn die Eingabe eine fachliche Frage, Folgefrage, "
            "Bitte um Erklaerung, Bitte um Quellen oder einen Arbeitsauftrag enthaelt. "
            "Beispiele fuer true: 'Danke', 'Danke dir', 'Vielen lieben Dank', 'Passt danke', "
            "'Hallo', 'Tschuess', 'Okay super'. "
            "Beispiele fuer false: 'Danke, kannst du mir noch die Quelle nennen?', "
            "'Was ist der Unterschied zwischen MPP und Leerlaufspannung?', "
            "'Erklaere das genauer'."
        )

        user_prompt = f"Nutzereingabe:\n{text}"

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return False

        return bool(data.get("is_smalltalk", False))

    def smalltalk_response(self) -> str:
        return "Hast du Fragen zu unseren Lehrvideos zu PV-Anlagen?"

    def is_relevant_by_score(
        self,
        retrieved_chunks: List[Dict[str, Any]],
        min_score: Optional[float] = None,
    ) -> bool:
        if not retrieved_chunks:
            return False

        if min_score is None:
            min_score = self.min_similarity_score

        return retrieved_chunks[0]["score"] >= min_score

    def classify_relevance_with_llm(self, user_query: str, context: str) -> bool:
        system_prompt = (
            "Du bist ein Klassifikator fuer Lehrvideoanfragen. "
            "Pruefe, ob die Nutzerfrage fachlich in den bereitgestellten Lehrvideoquellen behandelt wird. "
            "Antworte ausschliesslich mit JA oder NEIN. "
            "JA nur dann, wenn die Frage inhaltlich direkt oder sehr klar in den Quellen behandelt wird. "
            "NEIN, wenn die Treffer nur lose aehnlich sind, nur einzelne Woerter teilen oder die Antwort nicht wirklich in den Quellen vorkommt. "
            "Smalltalk ist immer NEIN."
        )

        user_prompt = (
            f"Nutzerfrage:\n{user_query}\n\n"
            f"Quellenkontext:\n{context}\n\n"
            "Ist die Frage fachlich Bestandteil der Lehrvideos? Antworte nur mit JA oder NEIN."
        )

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        answer = (response.choices[0].message.content or "").strip().upper()
        return answer == "JA"

    def classify_request_with_context(self, user_query: str, context: str) -> str:
        system_prompt = (
            "Du klassifizierst Nutzerfragen fuer einen Chatbot zu Lehrvideos ueber PV-Anlagen. "
            "Antworte ausschliesslich mit genau einer Klasse: NON_DOMAIN, DOMAIN_GENERIC, DOMAIN_SPECIFIC. "
            "NON_DOMAIN: Die Frage wird fachlich nicht wirklich in den Quellen behandelt. "
            "Smalltalk, Dank, Begruessung, Verabschiedung und reine Zustimmung sind immer NON_DOMAIN. "
            "DOMAIN_GENERIC: Die Frage betrifft die Quellen, ist aber zu breit, zu allgemein oder mehrdeutig "
            "und braucht vor der Beantwortung eine Konkretisierung. "
            "DOMAIN_SPECIFIC: Die Frage wird fachlich in den Quellen behandelt und ist konkret genug beantwortbar."
        )

        user_prompt = (
            f"Nutzerfrage:\n{user_query}\n\n"
            f"Quellenkontext:\n{context}\n\n"
            "Wie ist die Frage zu klassifizieren?"
        )

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        label = (response.choices[0].message.content or "").strip().upper()

        if label in {"NON_DOMAIN", "DOMAIN_GENERIC", "DOMAIN_SPECIFIC"}:
            return label
        return "NON_DOMAIN"

    def looks_like_follow_up(self, user_query: str) -> bool:
        text = self.normalize_whitespace(user_query).lower()

        follow_up_markers = [
            "damit",
            "dazu",
            "darauf",
            "und was ist mit",
            "gilt das auch",
            "wo steht das",
            "kannst du das",
            "was meinst du damit",
            "was ist mit",
            "und bei",
            "gilt das fuer",
            "gilt das auch fuer",
        ]

        if len(text.split()) <= 6:
            if text in {"und?", "wieso?", "warum?", "wie genau?", "wo genau?", "welche quelle?"}:
                return True

            for marker in follow_up_markers:
                if marker in text:
                    return True

        for marker in follow_up_markers:
            if marker in text:
                return True

        return False

    def detect_turn_type(self, user_query: str) -> str:
        if self.looks_like_follow_up(user_query):
            return "FOLLOW_UP"

        if not self.last_user_query and not self.last_selected_chunks:
            return "NEW_QUESTION"

        system_prompt = (
            "Du klassifizierst eine Nutzereingabe fuer einen Lehrvideo-Chatbot. "
            "Antworte ausschliesslich mit FOLLOW_UP oder NEW_QUESTION. "
            "FOLLOW_UP nur dann, wenn sich die Eingabe klar auf den vorherigen fachlichen Kontext bezieht, "
            "zum Beispiel durch Verweise wie 'das', 'dazu', 'und was ist mit', 'wo steht das', "
            "oder wenn die Eingabe ohne vorherigen Kontext nicht sinnvoll verstehbar waere. "
            "NEW_QUESTION, wenn eine neue eigenstaendige fachliche Frage gestellt wird."
        )

        last_context = self.last_topic_summary or self.last_user_query or ""
        user_prompt = (
            f"Vorheriger fachlicher Kontext:\n{last_context}\n\n"
            f"Aktuelle Eingabe:\n{user_query}\n\n"
            "Ist das eine Folgefrage oder eine neue Frage?"
        )

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        label = (response.choices[0].message.content or "").strip().upper()
        return "FOLLOW_UP" if label == "FOLLOW_UP" else "NEW_QUESTION"

    def is_query_too_generic(self, user_query: str, retrieved_chunks: List[Dict[str, Any]]) -> bool:
        context = self.build_selection_context(retrieved_chunks[:6])

        system_prompt = (
            "Du pruefst, ob eine fachliche Nutzerfrage fuer die Beantwortung aus Lehrvideoquellen "
            "zu allgemein oder mehrdeutig ist. "
            "Antworte nur mit JA oder NEIN. "
            "JA bedeutet: Die Frage ist zu generisch, umfasst mehrere moegliche Unterthemen "
            "oder braucht eine Praezisierung. "
            "NEIN bedeutet: Die Frage ist hinreichend konkret beantwortbar."
        )

        user_prompt = (
            f"Nutzerfrage:\n{user_query}\n\n"
            f"Moegliche passende Quellen:\n{context}\n\n"
            "Ist die Frage zu generisch und braucht vor der Beantwortung eine Konkretisierung? "
            "Antworte nur mit JA oder NEIN."
        )

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        answer = (response.choices[0].message.content or "").strip().upper()
        return answer == "JA"

    def build_clarification_options(self, user_query: str, retrieved_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        context = self.build_selection_context(retrieved_chunks[:8])

        system_prompt = (
            "Du gruppierst passende Lehrvideo-Quellen fuer eine zu allgemeine Nutzerfrage "
            "in thematische Rueckfrage-Optionen. "
            "Erzeuge 2 bis 5 klar unterscheidbare Themen. "
            "Jedes Thema soll einen kurzen, nutzerfreundlichen Titel haben. "
            "Ordne jedem Thema die passenden Quellen-Nummern zu. "
            "Antworte nur als JSON im Format: "
            "{\"options\": [{\"label\": \"...\", \"source_numbers\": [1,2]}]}."
        )

        user_prompt = (
            f"Nutzerfrage:\n{user_query}\n\n"
            f"Quellen:\n{context}\n\n"
            "Welche thematischen Rueckfrage-Optionen eignen sich, um die Nutzerfrage zu praezisieren?"
        )

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []

        if isinstance(data, dict) and isinstance(data.get("options"), list):
            options = data["options"]
        else:
            return []

        cleaned_options = []
        for option in options:
            if not isinstance(option, dict):
                continue

            label = self.normalize_whitespace(str(option.get("label", "")))
            source_numbers = option.get("source_numbers", [])

            if not label or not isinstance(source_numbers, list):
                continue

            valid_numbers = []
            for n in source_numbers:
                if isinstance(n, int) and 1 <= n <= len(retrieved_chunks) and n not in valid_numbers:
                    valid_numbers.append(n)

            if valid_numbers:
                cleaned_options.append(
                    {
                        "label": label,
                        "source_numbers": valid_numbers,
                    }
                )

        return cleaned_options[:5]

    def format_clarification_question(self, options: List[Dict[str, Any]]) -> str:
        if not options:
            return "Deine Frage ist noch zu allgemein. Bitte praezisiere, auf welchen Aspekt du dich beziehst."

        lines = ["Deine Frage ist noch etwas allgemein. Welchen Aspekt meinst du genau?"]
        for i, option in enumerate(options, start=1):
            label = option.get("label", "").strip()
            if label:
                lines.append(f"{i}. {label}")

        lines.append("Antworte einfach mit der Nummer oder dem Thema.")
        return "\n".join(lines)

    def resolve_clarification_option(self, user_query: str) -> Optional[int]:
        """Ermittelt den 0-basierten Index der gewaehlten Option.
        Erst regelbasiert (Nummer, Label), dann per LLM als Fallback."""
        if not self.pending_clarification:
            return None

        options = self.pending_clarification.get("options", [])
        if not options:
            return None

        normalized = self.normalize_whitespace(user_query).lower()

        # 1. Nummer in der Antwort ("2", "2.", "Nummer 2", "die zweite ist 2")
        number_match = re.search(r"\b(\d+)\b", normalized)
        if number_match:
            idx = int(number_match.group(1)) - 1
            if 0 <= idx < len(options):
                return idx

        # 2. Label-Treffer in beide Richtungen (Nutzer schreibt Label oder Teil davon)
        for i, option in enumerate(options):
            label = self.normalize_whitespace(option.get("label", "")).lower()
            if label and (label in normalized or normalized in label):
                return i

        # 3. LLM-Fallback: welche Option ist am ehesten gemeint?
        option_lines = "\n".join(
            f"{i + 1}. {option.get('label', '')}" for i, option in enumerate(options)
        )

        system_prompt = (
            "Du ordnest die Antwort eines Nutzers einer von mehreren Auswahl-Optionen zu. "
            "Der Nutzer wurde gefragt, welchen Aspekt er meint. "
            "Waehle die Option, die am ehesten gemeint ist - auch bei Tippfehlern, "
            "Abkuerzungen, Umschreibungen oder Teilangaben grosszuegig zuordnen. "
            'Antworte nur als JSON im Format: {"option": <Nummer>}. '
            'Nur wenn die Antwort offensichtlich zu keiner Option passt, antworte {"option": 0}.'
        )
        user_prompt = (
            f"Optionen:\n{option_lines}\n\n"
            f"Antwort des Nutzers:\n{user_query}\n\n"
            "Welche Option ist am ehesten gemeint?"
        )

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        raw = (response.choices[0].message.content or "").strip()
        try:
            idx = int(json.loads(raw).get("option", 0)) - 1
        except (ValueError, TypeError, json.JSONDecodeError):
            fallback = re.search(r"\d+", raw)
            idx = int(fallback.group(0)) - 1 if fallback else -1

        if 0 <= idx < len(options):
            return idx
        return None


    def summarize_topic(self, user_query: str, selected_chunks: List[Dict[str, Any]]) -> str:
        context = self.build_selection_context(selected_chunks[:3])

        system_prompt = (
            "Fasse das fachliche Thema der Nutzerfrage und der ausgewaehlten Quellen "
            "in einem sehr kurzen Satz zusammen. Maximal 15 Woerter."
        )

        user_prompt = (
            f"Nutzerfrage:\n{user_query}\n\n"
            f"Quellen:\n{context}\n\n"
            "Formuliere eine kurze Themenzusammenfassung."
        )

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        return self.normalize_whitespace(response.choices[0].message.content or "")

    def build_follow_up_query(self, user_query: str) -> str:
        previous = self.last_effective_query or self.last_user_query or ""
        topic = self.last_topic_summary or ""

        parts = []
        if previous:
            parts.append(f"Vorherige Frage: {previous}")
        if topic:
            parts.append(f"Thema: {topic}")
        parts.append(f"Folgefrage: {user_query}")

        return "\n".join(parts)

    def select_relevant_quotes(self, user_query: str, retrieved_chunks: List[Dict[str, Any]]) -> List[int]:
        context = self.build_selection_context(retrieved_chunks)

        system_prompt = (
            "Du waehlst aus bereitgestellten Lehrvideoquellen die fachlich passendsten woertlichen Textstellen fuer eine Nutzerfrage aus. "
            "Du darfst keine Antwort formulieren. "
            "Du darfst nur Quellen-Nummern auswaehlen. "
            "Waehle nur Quellen, deren Text die Nutzerfrage fachlich direkt beantwortet oder eindeutig behandelt. "
            "Wenn keine Quelle fachlich direkt passt, antworte nur mit: NONE\n"
            "Wenn genau eine Quelle direkt passt, antworte nur mit der Nummer, zum Beispiel: 2\n"
            "Wenn mehrere Quellen wirklich noetig sind, antworte nur mit kommaseparierten Nummern, zum Beispiel: 2,4\n"
            "Keine Erlaeuterung. Kein weiterer Text."
        )

        user_prompt = (
            f"Nutzerfrage:\n{user_query}\n\n"
            f"Quellen:\n{context}\n\n"
            "Welche Quelle oder Quellen behandeln die Frage fachlich direkt?"
        )

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        raw = (response.choices[0].message.content or "").strip()

        if raw.upper() == "NONE":
            return []

        matches = re.findall(r"\d+", raw)
        selected = []

        for m in matches:
            idx = int(m)
            if 1 <= idx <= len(retrieved_chunks) and idx not in selected:
                selected.append(idx)

        return selected

    def format_source(self, chunk: Dict[str, Any]) -> str:
        return (
            f"Modul {chunk['module_number']} - {chunk['module_name']} | "
            f"Video {chunk['video_number']} - {chunk['video_name']} | "
            f"{chunk['time_range']}"
        )

    def construct_answer_from_chunks(self, selected_chunks: List[Dict[str, Any]]) -> str:
        answer_blocks = []

        for chunk in selected_chunks:
            quote = chunk["text"].strip()
            source = self.format_source(chunk)
            answer_blocks.append(
                f'Zitat: "{quote}"\n'
                f"Quelle: {source}"
            )

        return "\n\n".join(answer_blocks)

    def validate_selected_chunks(
        self,
        selected_chunks: List[Dict[str, Any]],
    ) -> bool:
        if not selected_chunks:
            return False

        for chunk in selected_chunks:
            if not chunk.get("text", "").strip():
                return False
            if chunk.get("score", 0.0) < self.min_similarity_score:
                return False

        return True

    def answer_specific_question(self, user_query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
        selected_indices = self.select_relevant_quotes(user_query, retrieved_chunks)

        if not selected_indices:
            self.last_user_query = user_query
            self.last_answer_type = "non_domain"
            return "Kein Bestandteil der Lehrvideos"

        selected_chunks = [
            retrieved_chunks[i - 1]
            for i in selected_indices
            if 1 <= i <= len(retrieved_chunks)
        ]

        if not self.validate_selected_chunks(selected_chunks):
            self.last_user_query = user_query
            self.last_answer_type = "non_domain"
            return "Kein Bestandteil der Lehrvideos"

        answer = self.construct_answer_from_chunks(selected_chunks)

        self.last_user_query = user_query
        self.last_effective_query = user_query
        self.last_selected_chunks = selected_chunks
        self.last_topic_summary = self.summarize_topic(user_query, selected_chunks)
        self.last_answer_type = "source_answer"
        self.pending_clarification = None

        return answer

    def handle_new_question(self, user_query: str) -> str:
        retrieved_chunks = self.retrieve(user_query, top_k=self.retrieval_top_k)

        if not self.is_relevant_by_score(retrieved_chunks):
            self.last_user_query = user_query
            self.last_answer_type = "non_domain"
            return "Kein Bestandteil der Lehrvideos"

        context = self.build_selection_context(retrieved_chunks[:8])
        classification = self.classify_request_with_context(user_query, context)

        if classification == "NON_DOMAIN":
            self.last_user_query = user_query
            self.last_answer_type = "non_domain"
            return "Kein Bestandteil der Lehrvideos"

        if classification == "DOMAIN_GENERIC":
            options = self.build_clarification_options(user_query, retrieved_chunks[:8])
            self.pending_clarification = {
                "original_query": user_query,
                "retrieved_chunks": retrieved_chunks[:8],
                "options": options,
            }
            self.last_user_query = user_query
            self.last_answer_type = "clarification"
            return self.format_clarification_question(options)

        if classification == "DOMAIN_SPECIFIC":
            return self.answer_specific_question(user_query, retrieved_chunks)

        self.last_user_query = user_query
        self.last_answer_type = "non_domain"
        return "Kein Bestandteil der Lehrvideos"

    def handle_follow_up(self, user_query: str) -> str:
        local_candidates = self.last_selected_chunks[:]
        effective_query = self.build_follow_up_query(user_query)

        if local_candidates:
            selected_indices = self.select_relevant_quotes(effective_query, local_candidates)
            if selected_indices:
                selected_chunks = [
                    local_candidates[i - 1]
                    for i in selected_indices
                    if 1 <= i <= len(local_candidates)
                ]
                if self.validate_selected_chunks(selected_chunks):
                    answer = self.construct_answer_from_chunks(selected_chunks)
                    self.last_user_query = user_query
                    self.last_effective_query = effective_query
                    self.last_selected_chunks = selected_chunks
                    self.last_topic_summary = self.summarize_topic(effective_query, selected_chunks)
                    self.last_answer_type = "source_answer"
                    return answer

        retrieved_chunks = self.retrieve(effective_query, top_k=self.retrieval_top_k)

        if not self.is_relevant_by_score(retrieved_chunks):
            self.last_user_query = user_query
            self.last_answer_type = "non_domain"
            return "Kein Bestandteil der Lehrvideos"

        context = self.build_selection_context(retrieved_chunks[:8])
        classification = self.classify_request_with_context(effective_query, context)

        if classification == "DOMAIN_GENERIC":
            options = self.build_clarification_options(effective_query, retrieved_chunks[:8])
            self.pending_clarification = {
                "original_query": effective_query,
                "retrieved_chunks": retrieved_chunks[:8],
                "options": options,
            }
            self.last_user_query = user_query
            self.last_answer_type = "clarification"
            return self.format_clarification_question(options)

        if classification == "DOMAIN_SPECIFIC":
            return self.answer_specific_question(effective_query, retrieved_chunks)

        self.last_user_query = user_query
        self.last_answer_type = "non_domain"
        return "Kein Bestandteil der Lehrvideos"

    def handle_pending_clarification(self, user_query: str) -> Optional[str]:
        option_idx = self.resolve_clarification_option(user_query)

        if option_idx is not None:
            options = self.pending_clarification.get("options", [])
            retrieved_chunks = self.pending_clarification.get("retrieved_chunks", [])
            option = options[option_idx]
            label = option.get("label", "").strip()

            selected_chunks = [
                retrieved_chunks[i - 1]
                for i in option.get("source_numbers", [])
                if 1 <= i <= len(retrieved_chunks)
            ]
            if not selected_chunks:
                return "Ich konnte die Auswahl nicht eindeutig zuordnen. Bitte nenne den Aspekt noch etwas konkreter."

            original_query = self.pending_clarification.get("original_query", "")
            # WICHTIG: das Options-Label statt der Roh-Eingabe ("2.") verwenden,
            # damit die Zitatauswahl inhaltlich arbeiten kann
            effective_query = f"{original_query}\nPraezisierung: {label}"

            selected_indices = self.select_relevant_quotes(effective_query, selected_chunks)
            if selected_indices:
                final_chunks = [
                    selected_chunks[i - 1]
                    for i in selected_indices
                    if 1 <= i <= len(selected_chunks)
                ]
            else:
                # Fallback: statt Abbruch alle Quellen der gewaehlten Option nutzen
                final_chunks = selected_chunks

            if not self.validate_selected_chunks(final_chunks):
                return "Kein Bestandteil der Lehrvideos"

            answer = self.construct_answer_from_chunks(final_chunks)
            confirmation = f"Okay, du meinst also eher das {option_idx + 1}. Thema: {label}."
            answer = f"{confirmation}\n\n{answer}"

            self.last_user_query = user_query
            self.last_effective_query = effective_query
            self.last_selected_chunks = final_chunks
            self.last_topic_summary = self.summarize_topic(effective_query, final_chunks)
            self.last_answer_type = "source_answer"
            self.pending_clarification = None
            return answer

        if self.is_smalltalk(user_query):
            return self.smalltalk_response()

        return "Bitte antworte mit der Nummer oder formuliere kurz, welchen Aspekt du meinst."

    def ask(self, user_query: str) -> str:
        user_query = self.normalize_whitespace(user_query)

        if not user_query:
            return self.smalltalk_response()

        if self.pending_clarification:
            clarification_response = self.handle_pending_clarification(user_query)
            if clarification_response is not None:
                self.chat_history.append({"role": "user", "content": user_query})
                self.chat_history.append({"role": "assistant", "content": clarification_response})
                return clarification_response

        if self.is_smalltalk(user_query):
            answer = self.smalltalk_response()
            self.last_answer_type = "smalltalk"
            self.chat_history.append({"role": "user", "content": user_query})
            self.chat_history.append({"role": "assistant", "content": answer})
            return answer

        turn_type = self.detect_turn_type(user_query)

        if turn_type == "FOLLOW_UP":
            answer = self.handle_follow_up(user_query)
        else:
            answer = self.handle_new_question(user_query)

        self.chat_history.append({"role": "user", "content": user_query})
        self.chat_history.append({"role": "assistant", "content": answer})

        return answer

    def list_documents(self) -> None:
        print("\nVerfuegbare Lehrvideos:")
        for doc in self.documents:
            meta = self.parse_filename(doc["filename"])
            print(
                f"  [{doc['doc_id']}] "
                f"Modul {meta['module_number']} - {meta['module_name']} | "
                f"Video {meta['video_number']} - {meta['video_name']}"
            )

    def show_document(self, doc_id: int, max_chars: int = 1500) -> None:
        matches = [d for d in self.documents if d["doc_id"] == doc_id]
        if not matches:
            print("Lehrvideo nicht gefunden.")
            return

        doc = matches[0]
        meta = self.parse_filename(doc["filename"])

        print(
            f"\n--- Lehrvideo: Modul {meta['module_number']} - {meta['module_name']} | "
            f"Video {meta['video_number']} - {meta['video_name']} ---"
        )
        print("\nAusschnitt aus der hinterlegten Videoquelle:")
        print(doc["text"][:max_chars])

        if len(doc["text"]) > max_chars:
            print("\n... [gekuerzt] ...")

    def show_last_sources(self) -> None:
        if not self.last_retrieved_chunks:
            print("Noch keine Quellenstellen vorhanden.")
            return

        print("\nZuletzt verwendete Quellenstellen:")
        for i, chunk in enumerate(self.last_retrieved_chunks, start=1):
            preview = chunk["text"][:200].replace("\n", " ")
            print(
                f"[{i}] Modul {chunk.get('module_number', '')} - {chunk.get('module_name', '')} | "
                f"Video {chunk.get('video_number', '')} - {chunk.get('video_name', '')} | "
                f"Zeit: {chunk.get('time_range', '')} | "
                f"Relevanz: {chunk['score']}\n"
                f"    {preview}..."
            )