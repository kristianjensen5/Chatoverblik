import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MASTER_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

import chatoverblik  # noqa: E402


class NewProjectCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Masterversioner"
        self.root.mkdir()
        shutil.copytree(MASTER_ROOT / "context", self.root / "context")

    def tearDown(self):
        self.tmp.cleanup()

    def project_data(self, **overrides):
        data = {
            "name": "Sikker test",
            "type": "arbejde",
            "delivery": "iframe",
            "data": "persondata",
            "external_services": "ja",
            "source": "codex",
            "description": "Et kort til en superartikel.",
            "goal": "Byg den første verificerbare version.",
            "done_when": "Mobil og desktop er testet med screenshots.",
            "constraint": "Ingen deploy uden godkendelse.",
        }
        data.update(overrides)
        return data

    def test_creates_complete_bootstrap_and_routed_prompt(self):
        result = chatoverblik.create_or_prepare_project(
            self.root, self.project_data()
        )
        project = self.root / "Sikker test"
        expected = {
            "STATUS.md", "README.md", ".gitignore", "AGENTS.md", "CLAUDE.md",
            "LESSONS.md",
        }
        self.assertEqual(set(result["created"]), expected)
        self.assertEqual(
            {path.name for path in project.iterdir()}, expected
        )
        self.assertFalse((project / "index.html").exists())

        for filename in expected:
            content = (project / filename).read_text(encoding="utf-8")
            self.assertNotIn("{{", content, filename)
            self.assertNotIn("}}", content, filename)

        status = (project / "STATUS.md").read_text(encoding="utf-8")
        self.assertIn("**Leveringsform:** iframe", status)
        self.assertIn("**Data:** persondata", status)
        self.assertIn("**Eksterne services:** ja", status)

        prompt = result["first_prompt"]
        for relative_path in (
            "context/01_arbejdsgang.md",
            "context/03_security.md",
            "context/05_stopregler.md",
            "context/08_repo_politik.md",
            "context/08_backup_status.md",
            "context/02_brand.md",
            "context/02_iframe.md",
            "context/03_reader_data.md",
            "context/03_external_services.md",
            "context/03_iframe_platform.md",
        ):
            self.assertIn(relative_path, prompt)
        self.assertIn(str(self.root / "AGENTS.md"), prompt)
        self.assertNotIn("Memory", prompt)
        self.assertNotIn("Tre konkrete spørgsmål", prompt)
        self.assertNotIn("Sonnet/Haiku", prompt)
        self.assertNotIn("context/05_lessons.md", prompt)

        gitignore = (project / ".gitignore").read_text(encoding="utf-8")
        for pattern in (".env", ".dev.vars", "*.key", "data/", "private/"):
            self.assertIn(pattern, gitignore)

        agents = (project / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(str(self.root / "AGENTS.md"), agents)

    def test_missing_required_template_fails_before_project_is_created(self):
        template = self.root / "context" / "templates" / "project_AGENTS.md"
        template.unlink()

        with self.assertRaises(chatoverblik.ProjectSetupError) as caught:
            chatoverblik.create_or_prepare_project(
                self.root, self.project_data(name="Må ikke oprettes")
            )

        self.assertIn("Påkrævet fil mangler", str(caught.exception))
        self.assertFalse((self.root / "Må ikke oprettes").exists())

    def test_setup_capability_requires_complete_context(self):
        self.assertTrue(chatoverblik.project_setup_available(self.root))

        (self.root / "context" / "manifest.json").unlink()

        self.assertFalse(chatoverblik.project_setup_available(self.root))

    def test_frontend_requires_explicit_setup_capability(self):
        frontend = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn(
            'id="btn-new-project" class="sidebar-tool-btn" hidden', frontend
        )
        self.assertIn(
            'data.project_setup_available !== true', frontend
        )
        self.assertIn("submitButton.disabled = true", frontend)
        self.assertIn("!r.ok || !rd.ok", frontend)

    def test_existing_files_are_preserved(self):
        project = self.root / "Eksisterende"
        project.mkdir()
        original_status = "# Min status\n\nMå ikke overskrives.\n"
        (project / "STATUS.md").write_text(original_status, encoding="utf-8")

        data = self.project_data(name="ignored", existing_cwd=str(project))
        result = chatoverblik.create_or_prepare_project(self.root, data)

        self.assertTrue(result["reused"])
        self.assertIn("STATUS.md", result["skipped"])
        self.assertEqual(
            (project / "STATUS.md").read_text(encoding="utf-8"), original_status
        )
        self.assertIn("fortsætter arbejdet på", result["first_prompt"])
        self.assertFalse((project / "index.html").exists())

    def test_text_is_normalized_and_cannot_inject_template_tokens(self):
        result = chatoverblik.create_or_prepare_project(
            self.root,
            self.project_data(
                name="Renset tekst",
                description="  Første linje\n\nanden linje {{PROJECT_NAME}}  ",
            ),
        )
        readme = (self.root / "Renset tekst" / "README.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Første linje anden linje { {PROJECT_NAME} }", readme)
        self.assertNotIn("{{", readme)
        self.assertEqual(result["name"], "Renset tekst")

    def test_unicode_project_name_is_normalized_to_nfc(self):
        decomposed_name = "Me\u0301trique"

        result = chatoverblik.create_or_prepare_project(
            self.root, self.project_data(name=decomposed_name)
        )

        self.assertEqual(result["name"], "Métrique")
        self.assertTrue((self.root / "Métrique" / "STATUS.md").is_file())

    def test_existing_substantive_claude_file_blocks_setup(self):
        project = self.root / "Egne regler"
        project.mkdir()
        original = "# Vigtige projektregler\n\nMå ikke erstattes.\n"
        (project / "CLAUDE.md").write_text(original, encoding="utf-8")

        with self.assertRaises(chatoverblik.ProjectSetupError) as caught:
            chatoverblik.create_or_prepare_project(
                self.root,
                self.project_data(existing_cwd=str(project)),
            )

        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(
            (project / "CLAUDE.md").read_text(encoding="utf-8"), original
        )
        self.assertEqual({path.name for path in project.iterdir()}, {"CLAUDE.md"})

    def test_new_project_write_failure_leaves_no_partial_project(self):
        original_open = Path.open

        def fail_status_write(path, *args, **kwargs):
            mode = args[0] if args else kwargs.get("mode", "r")
            if (
                path.name == "STATUS.md"
                and path.parent.name.startswith(".command-center-project-")
                and mode == "x"
            ):
                raise OSError("simuleret skrivefejl")
            return original_open(path, *args, **kwargs)

        with mock.patch.object(Path, "open", fail_status_write):
            with self.assertRaisesRegex(OSError, "simuleret skrivefejl"):
                chatoverblik.create_or_prepare_project(
                    self.root, self.project_data(name="Atomisk test")
                )

        self.assertFalse((self.root / "Atomisk test").exists())
        self.assertEqual(
            list(self.root.glob(".command-center-project-*")), []
        )

    def test_licensed_content_routes_commercial_rules_without_external_service(self):
        metadata = chatoverblik.normalize_project_metadata(
            self.project_data(
                delivery="internt",
                data="licenseret",
                external_services="nej",
            )
        )

        selected = chatoverblik.select_context_documents(self.root, metadata)

        self.assertIn("context/03_external_services.md", selected)


if __name__ == "__main__":
    unittest.main()
