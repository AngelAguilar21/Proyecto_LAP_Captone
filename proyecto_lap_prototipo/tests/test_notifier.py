"""Mail configuration and cooldown with temporary storage and no SMTP."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import notifier


class NotifierTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="notifier-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.password = "synthetic-test-password-only"
        self.config = {
            "enabled": True,
            "host": "smtp.example.invalid",
            "port": 465,
            "user": "sender@example.invalid",
            "password": self.password,
            "recipients": ["recipient@example.invalid"],
        }
        self.send = self.enterContext(patch.object(notifier, "_send"))

    def test_public_config_does_not_expose_password(self):
        empty = notifier.public(self.root)
        self.assertNotIn("password", empty)
        self.assertFalse(empty["configured"])

        saved_public = notifier.save(self.root, self.config.copy())
        public = notifier.public(self.root)

        for response in (saved_public, public):
            with self.subTest(response=response):
                self.assertNotIn("password", response)
                self.assertNotIn(self.password, json.dumps(response))
                self.assertTrue(response["configured"])
                self.assertEqual(response["user"], self.config["user"])
                self.assertEqual(response["recipients"], self.config["recipients"])
        # The internal loader must still supply the credential to Mailer.
        self.assertEqual(notifier.load(self.root)["password"], self.password)
        self.send.assert_not_called()

    def test_empty_password_preserves_saved_password(self):
        notifier.save(self.root, self.config.copy())

        response = notifier.save(self.root, {"password": "", "port": 587})

        persisted = json.loads(notifier.path_for(self.root).read_text(encoding="utf-8"))
        self.assertEqual(persisted["password"], self.password)
        self.assertEqual(notifier.load(self.root)["password"], self.password)
        self.assertEqual(persisted["port"], 587)
        self.assertTrue(response["configured"])
        self.assertNotIn("password", response)
        self.assertNotIn(self.password, json.dumps(response))
        self.send.assert_not_called()

    def test_invalid_recipient_email_is_rejected(self):
        notifier.save(self.root, self.config.copy())
        before = notifier.path_for(self.root).read_bytes()

        for address in ("", "missing-at.example.invalid", None, 123,
                        "a" * 189 + "@example.com"):
            with self.subTest(address=address):
                with self.assertRaises(ValueError):
                    notifier.save(self.root, {"recipients": [address]})
                self.assertEqual(notifier.path_for(self.root).read_bytes(), before)
        self.send.assert_not_called()

    def test_invalid_port_is_rejected(self):
        notifier.save(self.root, self.config.copy())
        before = notifier.path_for(self.root).read_bytes()

        for port in (0, -1, 65536, "465", 465.0, True, False, None):
            with self.subTest(port=port):
                with self.assertRaises(ValueError):
                    notifier.save(self.root, {"port": port})
                self.assertEqual(notifier.path_for(self.root).read_bytes(), before)
        self.send.assert_not_called()

    def test_same_key_is_not_sent_again_until_cooldown_expires(self):
        notifier.save(self.root, self.config.copy())
        mailer = notifier.Mailer(self.root)
        # Replace only notifier's clock reference, not the shared time module.
        clock = self.enterContext(patch.object(notifier, "time", Mock()))
        start = 1000.0
        clock.time.return_value = start

        self.assertTrue(mailer.send("Alerta sintética", "Contenido de prueba",
                                   key="camera:crowd:1", blocking=True))
        self.send.assert_called_once_with(self.config, "Alerta sintética", "Contenido de prueba")
        self.assertEqual(mailer.sent, 1)

        for elapsed in (0, notifier.COOLDOWN / 2, notifier.COOLDOWN - 0.001):
            with self.subTest(elapsed=elapsed):
                clock.time.return_value = start + elapsed
                self.assertFalse(mailer.send("Alerta sintética", "Contenido de prueba",
                                            key="camera:crowd:1", blocking=True))
                self.assertEqual(self.send.call_count, 1)
                self.assertEqual(mailer.sent, 1)

        # A different key remains eligible while the first is cooling down.
        self.assertTrue(mailer.send("Otra alerta", "Otro contenido",
                                   key="camera:crowd:2", blocking=True))
        self.assertEqual(self.send.call_count, 2)
        self.assertEqual(mailer.sent, 2)

        clock.time.return_value = start + notifier.COOLDOWN
        self.assertTrue(mailer.send("Alerta sintética", "Contenido de prueba",
                                   key="camera:crowd:1", blocking=True))
        self.assertEqual(self.send.call_count, 3)
        self.send.assert_called_with(self.config, "Alerta sintética", "Contenido de prueba")
        self.assertEqual(mailer.sent, 3)
        self.assertIsNone(mailer.error)

    def test_first_key_at_zero_is_not_suppressed(self):
        notifier.save(self.root, self.config.copy())
        with patch.object(notifier, "time", Mock()) as clock:
            clock.time.return_value = 0
            self.assertTrue(notifier.Mailer(self.root).send("Test", "Test", key="new", blocking=True))
        self.send.assert_called_once()

    def test_alternative_recipients_do_not_modify_persisted_configuration(self):
        notifier.save(self.root, self.config.copy())
        before = notifier.path_for(self.root).read_bytes()
        mailer = notifier.Mailer(self.root)
        override = ["alternate@example.invalid"]
        self.assertTrue(mailer.send("Test", "Test", blocking=True, recipients=override))
        self.assertEqual(self.send.call_args.args[0]["recipients"], override)
        self.assertEqual(notifier.path_for(self.root).read_bytes(), before)
        with self.assertRaises(ValueError):
            mailer.send("Test", "Test", blocking=True, recipients=["invalid"])
        self.send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
