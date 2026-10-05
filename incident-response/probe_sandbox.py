"""Harmless runtime checks of the same permission profiles used by the responder."""
import json
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

from server import ROOT, permission_args


def main():
    results = []
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("Codex CLI unavailable")
    with tempfile.TemporaryDirectory(prefix="hw4-unrelated-canary-") as outside:
        canary = Path(outside) / "canary.txt"
        canary.write_text("HARMLESS_UNRELATED_CANARY")
        allowed = ROOT / "tests" / ".hw4-sandbox-canary"
        forbidden = ROOT / "incident-response" / ".hw4-sandbox-canary"
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        cases = [
            ("repository_read", "synthetic", ["/bin/cat", str(ROOT / "pyproject.toml")], True),
            ("unrelated_read", "synthetic", ["/bin/cat", str(canary)], False),
            ("synthetic_write", "synthetic", ["/bin/sh", "-c", 'printf harmless > "$1"', "probe", str(allowed)], False),
            ("real_scoped_write", "real", ["/bin/sh", "-c", 'printf harmless > "$1"', "probe", str(allowed)], True),
            ("real_outside_write", "real", ["/bin/sh", "-c", 'printf harmless > "$1"', "probe", str(forbidden)], False),
            ("network", "real", ["/usr/bin/nc", "-z", "-w", "1", "127.0.0.1", str(port)], False),
        ]
        try:
            for name, mode, args, permitted in cases:
                command = [codex, "sandbox", "-P", "hw4-responder", "-C", str(ROOT), *permission_args(mode), *args]
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                success = result.returncode == 0
                if "sandbox_apply" in result.stderr:
                    raise RuntimeError("Nested sandbox prevented validation; use approved host launch")
                results.append({"name": name, "argv": command, "exit_code": result.returncode,
                                "stdout": result.stdout, "stderr": result.stderr,
                                "expected_allowed": permitted, "pass": success == permitted})
        finally:
            listener.close()
            allowed.unlink(missing_ok=True)
            forbidden.unlink(missing_ok=True)
    output = ROOT / "incident-response" / "sandbox-probes.json"
    output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"pass": all(item["pass"] for item in results), "evidence": str(output),
                      "results": [{"name": item["name"], "pass": item["pass"]} for item in results]}, indent=2))
    if not all(item["pass"] for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
