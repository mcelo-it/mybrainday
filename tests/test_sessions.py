import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from backend.sessions import SessionStore, SessionNotFound, SessionCapacityExceeded


class SessionTests(unittest.TestCase):
    def test_isolation_rollback_and_history_limit(self):
        store = SessionStore(max_history_messages=4)
        with store.transaction() as (a, state):
            state.pending_clarification = {"options": [{"label": "A"}]}
            state.chat_history = [{"content": str(i)} for i in range(8)]
        with store.transaction() as (b, state):
            self.assertIsNone(state.pending_clarification)
        self.assertNotEqual(a, b)
        with self.assertRaises(RuntimeError):
            with store.transaction(a) as (_, state):
                state.pending_clarification["options"][0]["label"] = "corrupt"
                raise RuntimeError("provider failed")
        with store.transaction(a) as (_, state):
            self.assertEqual(state.pending_clarification["options"][0]["label"], "A")
            self.assertEqual(len(state.chat_history), 4)

    def test_expiry_capacity_unknown_and_failed_creation(self):
        now = [0]
        store = SessionStore(ttl_seconds=10, max_sessions=1, clock=lambda: now[0])
        with self.assertRaises(RuntimeError):
            with store.transaction():
                raise RuntimeError()
        with store.transaction() as (token, _):
            now[0] = 20
            with self.assertRaises(SessionCapacityExceeded):
                with store.transaction():
                    pass
        now[0] = 31
        with self.assertRaises(SessionNotFound):
            with store.transaction(token):
                pass
        with self.assertRaises(SessionNotFound):
            with store.transaction("client-invented"):
                pass
        with store.transaction() as (new_token, _):
            self.assertNotEqual(new_token, token)

    def test_same_session_serialized_other_session_independent(self):
        store = SessionStore()
        with store.transaction() as (a, _):
            pass
        with store.transaction() as (b, _):
            pass
        started, entered = Event(), Event()

        def second_turn():
            started.set()
            with store.transaction(a) as (_, state):
                entered.set()
                self.assertEqual(state.last_user_query, "first")
                state.last_user_query = "second"

        with ThreadPoolExecutor(max_workers=1) as pool:
            with store.transaction(a) as (_, state):
                future = pool.submit(second_turn)
                self.assertTrue(started.wait(2))
                self.assertFalse(entered.wait(0.05))
                with store.transaction(b) as (_, other):
                    other.last_user_query = "independent"
                state.last_user_query = "first"
            future.result(timeout=2)
        with store.transaction(a) as (_, state):
            self.assertEqual(state.last_user_query, "second")


if __name__ == "__main__":
    unittest.main()
