"""Tests for _wait_for_ide_ready() — klarsignal-ventelogikken der erstatter
det gamle faste time.sleep() i /api/open-in-windsurf.

Se aabne-projekt-plan.md for baggrund: en lock-fil i ~/.claude/ide/*.lock er
det eneste pålidelige "dette VS Code-vindue er klar til netop dette projekt"
signal Claude-udvidelsen giver os.
"""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import chatoverblik  # noqa: E402


class WaitForIdeReadyCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lock_dir = Path(self.tmp.name) / "ide"
        self.lock_dir.mkdir(parents=True)
        self.old_lock_dir = chatoverblik.IDE_LOCK_DIR
        chatoverblik.IDE_LOCK_DIR = self.lock_dir

        self.workspace = Path(self.tmp.name) / "Masterversioner" / "Nyelands drømmeverden"
        self.workspace.mkdir(parents=True)

    def tearDown(self):
        chatoverblik.IDE_LOCK_DIR = self.old_lock_dir
        self.tmp.cleanup()

    def _write_lock(self, name, workspace_folder, mtime=None, pid=1234):
        f = self.lock_dir / name
        f.write_text(json.dumps({
            "pid": pid,
            "workspaceFolders": [workspace_folder],
            "ideName": "Visual Studio Code",
            "transport": "ws",
            "runningInWindows": False,
            "authToken": "x",
        }), encoding="utf-8")
        if mtime is not None:
            import os
            os.utime(f, (mtime, mtime))

    def test_1_lock_file_appears_after_delay_returns_wait_time(self):
        """Lock-fil dukker op efter ~1 s → returnerer en ventetid, ikke None."""
        since_ts = time.time()

        def writer():
            time.sleep(1.0)
            self._write_lock("42.lock", str(self.workspace))

        t = chatoverblik.threading.Thread(target=writer, daemon=True)
        t.start()
        result = chatoverblik._wait_for_ide_ready(
            str(self.workspace), since_ts, timeout=10.0, interval=0.2)
        t.join()
        self.assertIsNotNone(result)
        self.assertGreater(result, 0)

    def test_2_lock_file_never_appears_returns_none_within_timeout(self):
        """Lock-fil dukker aldrig op → returnerer None inden for timeout."""
        since_ts = time.time()
        start = time.time()
        result = chatoverblik._wait_for_ide_ready(
            str(self.workspace), since_ts, timeout=1.5, interval=0.2)
        elapsed = time.time() - start
        self.assertIsNone(result)
        # Skal faktisk have ventet ca. timeout, ikke returneret med det samme
        self.assertGreaterEqual(elapsed, 1.4)

    def test_3_stale_lock_file_for_same_workspace_is_ignored(self):
        """Forældet lock-fil (mtime 3 dage tilbage) for samme mappe →
        ignoreres, returnerer None."""
        since_ts = time.time()
        stale_mtime = time.time() - 3 * 86400
        self._write_lock("99.lock", str(self.workspace), mtime=stale_mtime)
        result = chatoverblik._wait_for_ide_ready(
            str(self.workspace), since_ts, timeout=1.5, interval=0.2)
        self.assertIsNone(result)

    def test_4_danish_nfd_lock_matches_nfc_query(self):
        """Dansk mappenavn skrevet NFD i lock-filen og NFC i forespørgslen
        (fx 'drømmeverden') → matcher alligevel."""
        import unicodedata
        since_ts = time.time()
        # Skriv workspace-stien i lock-filen som NFD (macOS-stil dekomponeret)
        nfd_path = unicodedata.normalize("NFD", str(self.workspace))
        self._write_lock("7.lock", nfd_path)
        # Forespørg med den almindelige (NFC) sti
        nfc_query = unicodedata.normalize("NFC", str(self.workspace))
        result = chatoverblik._wait_for_ide_ready(
            nfc_query, since_ts, timeout=3.0, interval=0.2)
        self.assertIsNotNone(result)


class AlreadyOpenCase(WaitForIdeReadyCase):
    """`already_open` i /api/open-in-windsurf afgør om vi skal vente på en NY
    klarmelding eller bare fyre kommandoen mod et vindue der allerede står
    åbent. Den må ikke afgøres af lock-filens alder: udvidelsen skriver filen
    én gang ved opstart, så et vindue der har stået åbent siden i går, har en
    lock-fil fra i går. Vi bruger derfor processens liv, ikke filens alder."""

    def _live(self):
        return _ide_norm(self.workspace) in chatoverblik._ide_lock_workspaces(
            live_pid_only=True)

    def test_5_lock_from_dead_process_counts_as_not_open(self):
        """Lock-fil efter et lukket/kollapset VS Code (død pid) → projektet
        tælles IKKE som åbent, så vi venter på en rigtig klarmelding."""
        dead_pid = _find_dead_pid()
        self._write_lock("101.lock", str(self.workspace), pid=dead_pid)
        self.assertFalse(self._live())

    def test_6_old_lock_from_live_process_counts_as_open(self):
        """Lock-fil fra i forgårs, men processen lever → projektet ER åbent.
        Det er tilfældet en ren mtime-grænse ville tage fejl af."""
        import os
        self._write_lock("102.lock", str(self.workspace),
                         mtime=time.time() - 3 * 86400, pid=os.getpid())
        self.assertTrue(self._live())


def _ide_norm(p):
    return chatoverblik._norm_path(str(p))


def _find_dead_pid():
    """Find et pid der med sikkerhed ikke kører."""
    import os
    for candidate in range(90000, 99999):
        try:
            os.kill(candidate, 0)
        except ProcessLookupError:
            return candidate
        except Exception:
            continue
    raise RuntimeError("fandt ikke et ledigt pid")


if __name__ == "__main__":
    unittest.main()
