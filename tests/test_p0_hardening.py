import email.message
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import chatoverblik  # noqa: E402


class HardeningCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Masterversioner"
        self.project = self.root / "SafeProject"
        self.project.mkdir(parents=True)
        (self.project / "index.html").write_text("<h1>ok</h1>", encoding="utf-8")
        (self.project / "app.py").write_text("print('ok')\n", encoding="utf-8")
        (self.project / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
        (self.project / "data").mkdir()
        (self.project / "data" / "private.csv").write_text("a,b\n", encoding="utf-8")
        (self.project / "source-notes").mkdir()
        (self.project / "source-notes" / "note.md").write_text("source", encoding="utf-8")

        self.old_root = chatoverblik.MASTERVERSIONER_ROOT
        self.old_key = chatoverblik.ANTHROPIC_KEY
        chatoverblik.MASTERVERSIONER_ROOT = self.root
        chatoverblik.ANTHROPIC_KEY = "fake-key"
        with chatoverblik.STATE_LOCK:
            chatoverblik.STATE["sessions"] = [{
                "source": "codex",
                "id": "s1",
                "cwd": str(self.project),
                "project": "SafeProject",
                "first_user": "Lav noget med følsomme noter",
                "msg_count": 1,
                "file": str(self.project / "missing.jsonl"),
            }]
            chatoverblik.STATE["projects"] = [{
                "name": "SafeProject",
                "cwd": str(self.project),
                "chats": 1,
            }]
            chatoverblik.STATE["cache"] = {}
            chatoverblik.STATE["preview_tokens"] = {}

    def tearDown(self):
        chatoverblik.MASTERVERSIONER_ROOT = self.old_root
        chatoverblik.ANTHROPIC_KEY = self.old_key
        self.tmp.cleanup()

    def test_csrf_blocks_missing_or_cross_origin_post(self):
        handler = object.__new__(chatoverblik.Handler)
        handler.headers = email.message.Message()
        self.assertTrue(handler._is_csrf())

        handler.headers["Origin"] = "https://evil.example"
        self.assertTrue(handler._is_csrf())

        handler.headers.replace_header("Origin", f"http://localhost:{chatoverblik.PORT}")
        self.assertFalse(handler._is_csrf())

    def test_old_rce_route_is_not_registered(self):
        source = (ROOT / "chatoverblik.py").read_text(encoding="utf-8")
        self.assertNotIn('self.path == "/api/open-in-terminal"', source)
        self.assertNotIn("/api/open-in-terminal", (ROOT / "index.html").read_text(encoding="utf-8"))

    def test_path_traversal_and_secret_denylist(self):
        with self.assertRaises(chatoverblik.PathValidationError):
            chatoverblik.validate_canonical_path("/etc/passwd", purpose="file-content",
                                                want_dir=False)
        with self.assertRaises(chatoverblik.PathValidationError) as cm:
            chatoverblik.validate_canonical_path(self.project / ".env",
                                                purpose="file-content",
                                                want_dir=False)
        self.assertIn("Secrets", str(cm.exception))

    def test_file_tree_filters_data_and_source_notes(self):
        tree = chatoverblik.build_file_tree(self.project)
        names = {item["name"] for item in tree}
        self.assertIn("app.py", names)
        self.assertNotIn(".env", names)
        self.assertNotIn("data", names)
        self.assertNotIn("source-notes", names)

    def test_move_chat_and_preview_block_sensitive_paths(self):
        with self.assertRaises(chatoverblik.PathValidationError):
            chatoverblik.validate_canonical_path(self.project / "data",
                                                purpose="move-chat",
                                                want_dir=True,
                                                allowed_roots=[self.root])
        with self.assertRaises(chatoverblik.PathValidationError):
            chatoverblik.validate_canonical_path(self.project / "data" / "private.csv",
                                                purpose="preview",
                                                want_dir=False,
                                                allowed_roots=[self.project])

    def test_sensitive_ai_chat_requires_payload_confirmation(self):
        session = chatoverblik.STATE["sessions"][0]
        payload = chatoverblik.build_title_payload(session)
        ok, response, status = chatoverblik.require_ai_confirmation(
            {}, action="regenerate-title", model=chatoverblik.MODEL,
            payload=payload, sensitivity="chat"
        )
        self.assertFalse(ok)
        self.assertEqual(status, 409)
        self.assertTrue(response["requires_confirmation"])
        self.assertIn("Lav noget med følsomme noter", response["payload"])
        self.assertRegex(response["payload_sha256"], r"^[a-f0-9]{64}$")

    def test_csp_is_strict_for_app_and_api(self):
        nonce_csp = chatoverblik.APP_CSP.format(nonce="abc")
        self.assertIn("script-src 'self' 'nonce-abc'", nonce_csp)
        self.assertIn("object-src 'none'", nonce_csp)
        self.assertIn("default-src 'none'", chatoverblik.API_CSP)


class ReleaseCheckCase(unittest.TestCase):
    def test_release_check_passes_and_blocks_legacy_artifacts(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "release_check.py"), "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["ok"])
        self.assertEqual(data["package"], "Chatoverblik-current.zip")
        self.assertTrue(any("legacy blocked" in item for item in data["evidence"]))


if __name__ == "__main__":
    unittest.main()
