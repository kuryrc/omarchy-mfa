"""Own one Wayland source until expiry; paste requires an explicit hidden-panel ack."""

import json
import os
import secrets
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import IO

from core import MfaError, object_fields, string_field, totp
from models import Account
from store import runtime_dir


def read_reply(stream: IO[bytes], field: str) -> None:
    with selectors.DefaultSelector() as selector:
        selector.register(stream, selectors.EVENT_READ)
        if not selector.select(timeout=4):
            raise MfaError("clipboard_failed")
        reply = object_fields(json.loads(stream.readline()), "clipboard_failed")
    if reply.get(field) is not True:
        raise MfaError("clipboard_failed")


def stop_process(child: subprocess.Popen[bytes]) -> None:
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=1)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def close_pipes(worker: subprocess.Popen[bytes]) -> None:
    for stream in (worker.stdin, worker.stdout):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


class Clipboard:
    def __init__(self) -> None:
        self.pending: tuple[str, subprocess.Popen[bytes]] | None = None
        self.workers: list[subprocess.Popen[bytes]] = []

    def cancel(self) -> None:
        """Closing the control pipe cancels paste, but leaves copied content to expire."""
        if self.pending is not None:
            _, worker = self.pending
            self.pending = None
            close_pipes(worker)

    def copy(self, account: Account, paste: bool = False) -> str | None:
        self.cancel()
        now = time.time()
        payload = {
            "code": totp(account, now),
            "expiresAt": (int(now // account["period"]) + 1) * account["period"],
        }
        try:
            worker = subprocess.Popen(
                [sys.executable, "-B", str(Path(__file__).resolve()), "worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            raise MfaError("clipboard_failed") from None
        self.workers = [child for child in self.workers if child.poll() is None]
        self.workers.append(worker)
        assert worker.stdin is not None and worker.stdout is not None
        try:
            worker.stdin.write((json.dumps(payload) + "\n").encode())
            worker.stdin.flush()
            read_reply(worker.stdout, "ready")
            if paste:
                token = secrets.token_hex(16)
                self.pending = token, worker
                return token
        except (MfaError, ValueError, OSError):
            stop_process(worker)
            raise MfaError("clipboard_failed") from None
        finally:
            if self.pending is None:
                close_pipes(worker)
        return None

    def paste(self, token: str) -> None:
        if self.pending is None or token != self.pending[0]:
            raise MfaError("paste_expired")
        _, worker = self.pending
        try:
            assert worker.stdin is not None and worker.stdout is not None
            worker.stdin.write(b'{"paste":true}\n')
            worker.stdin.flush()
            read_reply(worker.stdout, "pasted")
        except (MfaError, ValueError, OSError):
            raise MfaError("paste_failed") from None
        finally:
            self.cancel()


def clipboard_worker() -> None:
    """An EOF cancels pending paste. Expiry destroys only our own clipboard source."""
    child: subprocess.Popen[bytes] | None = None

    def terminate(_signal: int, _frame: object) -> None:
        raise SystemExit()

    signal.signal(signal.SIGTERM, terminate)
    try:
        payload = object_fields(json.loads(sys.stdin.readline(4096)), "clipboard_failed")
        code = string_field(payload.get("code"), "clipboard_failed")
        deadline = float(str(payload.get("expiresAt")))
        if (
            not code.isascii()
            or not code.isdecimal()
            or len(code) not in (6, 7, 8)
            or not time.time() < deadline
        ):
            raise MfaError("clipboard_failed")
        env = dict(os.environ, TMPDIR=str(runtime_dir()))
        child = subprocess.Popen(
            ["wl-copy", "--foreground", "--sensitive", "--type", "text/plain"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        assert child.stdin is not None
        child.stdin.write(code.encode())
        child.stdin.close()
        time.sleep(0.05)
        if child.poll() is not None or time.time() >= deadline:
            raise MfaError("clipboard_failed")
        print(json.dumps({"ready": True}), flush=True)
        with selectors.DefaultSelector() as selector:
            selector.register(sys.stdin, selectors.EVENT_READ)
            while child.poll() is None and time.time() < deadline:
                timeout = min(0.1, max(0, deadline - time.time()))
                if selector.get_map():
                    if not selector.select(timeout):
                        continue
                    command = sys.stdin.readline(4096)
                    selector.unregister(sys.stdin)
                    if not command:
                        continue
                    fields = object_fields(json.loads(command), "paste_failed")
                    remaining = deadline - time.time()
                    if (
                        fields.get("paste") is not True
                        or remaining <= 0
                        or child.poll() is not None
                    ):
                        raise MfaError("paste_failed")
                    result = subprocess.run(
                        ["wtype", "-M", "shift", "-k", "Insert", "-m", "shift"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=min(3, remaining),
                        check=False,
                    )
                    print(json.dumps({"pasted": result.returncode == 0}), flush=True)
                else:
                    time.sleep(timeout)
    except Exception:
        # Payloads and subprocess errors can contain secrets. Only status leaves here.
        try:
            print(json.dumps({"ready": False, "pasted": False}), flush=True)
        except BrokenPipeError:
            pass
    finally:
        if child is not None:
            stop_process(child)


if __name__ == "__main__":
    clipboard_worker()
