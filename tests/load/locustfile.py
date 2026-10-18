import random

from locust import HttpUser, between, task


QUESTIONS = [
    "Was ist die Leerlaufspannung?",
    "Was versteht man unter dem MPP?",
    "Wie funktioniert ein Wechselrichter?",
    "Was ist der Unterschied zwischen Reihen- und Parallelschaltung?",
    "Welche Aufgabe hat ein PV-Modul?",
    "Was bedeutet Kurzschlussstrom?",
    "Wie verändert sich der Strom bei einer Parallelschaltung?",
    "Wie verändert sich die Spannung bei einer Reihenschaltung?",
]

FOLLOW_UPS = [
    "Kannst du mir dazu die Quelle nennen?",
    "Wo genau steht das?",
    "Kannst du das genauer erklären?",
]


class ChatbotUser(HttpUser):
    """Simuliert einen eigenständigen Teilnehmer mit eigener Conversation-ID."""

    wait_time = between(12, 30)

    def on_start(self):
        self.conversation_id = None
        self.has_asked_initial_question = False

    def _headers(self):
        headers = {}
        if self.conversation_id:
            headers["X-Conversation-ID"] = self.conversation_id
        return headers

    def _post_chat(self, message: str, request_name: str):
        with self.client.post(
            "/chat",
            json={
                "message": message,
                "include_diagnostics": False,
                "include_evidence_debug": False,
            },
            headers=self._headers(),
            name=request_name,
            catch_response=True,
            timeout=60,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"HTTP {response.status_code}: {response.text[:500]}"
                )
                return False

            try:
                data = response.json()
            except ValueError:
                response.failure("Antwort ist kein gültiges JSON")
                return False

            conversation_id = data.get("conversation_id")
            answer = data.get("answer")

            if not conversation_id:
                response.failure("conversation_id fehlt in der Antwort")
                return False

            if not answer or not isinstance(answer, str):
                response.failure("answer fehlt oder ist leer")
                return False

            if self.conversation_id and conversation_id != self.conversation_id:
                response.failure("Conversation-ID hat sich unerwartet geändert")
                return False

            self.conversation_id = conversation_id
            return True

    @task(4)
    def ask_initial_or_new_question(self):
        question = random.choice(QUESTIONS)
        if self._post_chat(question, "POST /chat - Fachfrage"):
            self.has_asked_initial_question = True

    @task(1)
    def ask_follow_up(self):
        if not self.has_asked_initial_question or not self.conversation_id:
            return
        self._post_chat(
            random.choice(FOLLOW_UPS),
            "POST /chat - Folgefrage",
        )
