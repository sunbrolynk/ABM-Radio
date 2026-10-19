"""Runs check-public.sh against throwaway repos. The bad strings are assembled at runtime, so this
file itself passes the check it tests."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check-public.sh"
NOREPLY = "1+someone@users.noreply.github.com"


class CheckPublicTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "someone")
        self.git("config", "user.email", NOREPLY)
        (self.repo / "scripts").mkdir()
        shutil.copy(SCRIPT, self.repo / "scripts" / "check-public.sh")

    def git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def check(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "scripts/check-public.sh", *args], cwd=self.repo, capture_output=True, text=True
        )

    def staged(self, text: str | bytes, name: str = "notes.md") -> subprocess.CompletedProcess[str]:
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if isinstance(text, bytes) else text.encode())
        self.git("add", "-A")
        return self.check()

    def assertBlocked(self, text: str | bytes, reason: str, name: str = "notes.md") -> None:
        result = self.staged(text, name)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(reason, result.stderr)

    def test_clean_tree_passes_including_the_script_itself(self) -> None:
        result = self.staged("Streams live at https://stream.example.com/listen/lofi\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_private_addresses_are_blocked(self) -> None:
        for addr in ("192." + "168.1.20", "10." + "0.0.5", "172." + "20.1.1", "100." + "100.1.1", "169." + "254.3.4", "fd" + "12:3456::1", "fe" + "80::1"):
            with self.subTest(addr=addr):
                self.assertBlocked(f"box at {addr}\n", "IP")

    def test_lan_hostnames_are_blocked(self) -> None:
        for host, suffix in (("nas", "lan"), ("box", "local"), ("box", "localdomain"), ("nas", "home"), ("dc", "corp"), ("node.tail1234", "ts.net")):
            with self.subTest(suffix=suffix):
                self.assertBlocked(f"see {host}.{suffix}\n", "hostname")

    def test_bare_host_urls_are_blocked(self) -> None:
        scheme = "http" + "://"
        for text in (
            f"see {scheme}radiobox",
            f"({scheme}radiobox)",
            f'"{scheme}radiobox"',
            f"{scheme}radiobox?x=1",
            f"{scheme}radiobox#frag",
            f"{scheme}radiobox:8000/admin",
            f"{scheme}user@nas/",
            "ssh" + "://nas/x",
            "smb" + "://nas/share",
        ):
            with self.subTest(text=text):
                self.assertBlocked(text + "\n", "hostname")

    def test_public_dotted_urls_pass(self) -> None:
        result = self.staged("https" + "://radio.audiobookmanager.com/lofi and ssh" + "://git@github.com/x\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_lan_and_home_paths_are_blocked(self) -> None:
        for text in ("/" + "mnt/music", "/" + "srv/radio", "/" + "home/shane/music", "/" + "Users/shane", "\\\\" + "nas\\share", "C:" + "\\" + "Users" + "\\" + "shane"):
            with self.subTest(text=text):
                self.assertBlocked(f"media lives in {text}\n", "home path")

    def test_node_names_are_blocked(self) -> None:
        (self.repo / ".infra-names").write_text("tardis\n")
        (self.repo / ".gitignore").write_text(".infra-names\n")
        self.assertBlocked("runs on tardis\n", ".infra-names")

    def test_voice_and_markers_are_blocked(self) -> None:
        self.assertBlocked("W" + "e built this\n", "voice")
        self.assertBlocked("Co-Authored" + "-By: someone\n", "voice")

    def test_binary_files_are_blocked(self) -> None:
        self.assertBlocked(b"\x00\x01binary", "binary", name="cover.bin")

    def test_commit_message_is_checked(self) -> None:
        msg = self.repo / "msg"
        msg.write_text("add tracks\n\nGenerated " + "with a tool\n")
        result = self.check("--msg", str(msg))
        self.assertEqual(result.returncode, 1)

    def test_history_rejects_a_personal_email(self) -> None:
        self.staged("fine\n")
        self.git("-c", "user.email=me" + "@example.com", "commit", "-q", "-m", "x")
        result = self.check("--history")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no-reply", result.stderr)

    def test_history_accepts_noreply_emails(self) -> None:
        self.staged("fine\n")
        self.git("commit", "-q", "-m", "x")
        self.assertEqual(self.check("--history").returncode, 0)


if __name__ == "__main__":
    unittest.main()
