import unittest
import sys
import types
from unittest.mock import patch

sys.modules.setdefault("requests", types.SimpleNamespace(get=None, post=None))

import pensieri_random as pr


class ProcessDueSlotsTest(unittest.TestCase):
    def config(self, **overrides):
        config = pr.normalize_config({})
        config.update(overrides)
        return config

    def test_normalizes_paused_string(self):
        self.assertTrue(pr.normalize_config({"paused": "true"})["paused"])
        self.assertFalse(pr.normalize_config({"paused": "false"})["paused"])

    def test_sends_at_most_one_due_slot_per_run(self):
        state = {
            "date": "2026-08-07",
            "slots": [
                {"time": "09:30", "sent": False},
                {"time": "10:00", "sent": False},
            ],
        }
        sent = []

        with (
            patch.object(pr, "send_notification", side_effect=lambda text: sent.append(text) or True),
            patch.object(pr.random, "choice", side_effect=lambda choices: choices[0]),
        ):
            changed = pr.process_due_slots(
                state,
                ["Primo pensiero", "Secondo pensiero"],
                self.config(min_gap_minutes=30),
                pr.time_to_minutes("10:15"),
            )

        self.assertTrue(changed)
        self.assertEqual(sent, ["Primo pensiero"])
        self.assertTrue(state["slots"][0]["sent"])
        self.assertFalse(state["slots"][1]["sent"])
        self.assertEqual(state["last_sent_time"], "10:15")
        self.assertEqual(state["last_sent_slot_time"], "09:30")

    def test_skips_stale_slots_without_sending(self):
        state = {
            "date": "2026-08-07",
            "slots": [{"time": "09:00", "sent": False}],
        }

        with patch.object(pr, "send_notification") as send_notification:
            changed = pr.process_due_slots(
                state,
                ["Primo pensiero"],
                self.config(min_gap_minutes=90),
                pr.time_to_minutes("12:00"),
            )

        self.assertTrue(changed)
        self.assertTrue(state["slots"][0]["sent"])
        send_notification.assert_not_called()


if __name__ == "__main__":
    unittest.main()
