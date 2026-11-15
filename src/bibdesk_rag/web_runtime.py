"""Per-configuration localhost server discovery, locking and explicit lifecycle."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
from http.client import HTTPConnection, HTTPException
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import time
import webbrowser

from .config import config_selection, load_config
from .database import connect
from .web import WebApp, bind_server

START_TIMEOUT = 20


class ServerBusy(ValueError):
    pass


class Runtime:
    def __init__(self, config_path, config):
        self.config_path = config_path.resolve()
        self.directory = config.database.parent / "web-runtime"
        self.key = hashlib.sha256(os.fsencode(self.config_path)).hexdigest()
        self.path = self.directory / (self.key + ".json")
        self.lock_path = self.directory / (self.key + ".lock")
        self.lease_path = self.directory / (self.key + ".server.lock")
        sources = [config.bib, self.config_path, config.database,
                   *(Path(str(config.database) + suffix) for suffix in ("-wal", "-shm", "-journal"))]
        if config.database.is_file():
            db = connect(config.database, readonly=True, bib=config.bib)
            try:
                sources.extend(Path(row[0]) for row in db.execute("SELECT path FROM attachments"))
            finally:
                db.close()
        if any(path.resolve().is_relative_to(self.directory.resolve()) for path in sources):
            raise ValueError("Web runtime data overlaps a source, configuration or index path.")
        # The database directory is selected application data, never a venv or source library.
        if self.directory.is_symlink():
            raise ValueError("The web runtime directory must not be a symbolic link.")
        self.directory.mkdir(mode=0o700, parents=False, exist_ok=True)
        info = self.directory.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("The web runtime directory must be owned by you with permissions 0700.")

    @contextmanager
    def lock(self):
        fd = self.open_lock(self.lock_path)
        try:
            deadline = time.monotonic() + START_TIMEOUT + 5
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise ValueError("Another GUI command is busy. Please retry.") from None
                    time.sleep(0.05)
            yield fd
        finally:
            os.close(fd)

    @staticmethod
    def open_lock(path):
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
            os.close(fd)
            raise ValueError("Unsafe web runtime lock file.")
        return fd

    def acquire_lease(self):
        fd = self.open_lock(self.lease_path)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise ServerBusy("The GUI server is busy or shutting down. Please retry shortly.") from None
        return fd

    def lease_held(self):
        try:
            fd = self.acquire_lease()
        except ServerBusy:
            return True
        os.close(fd)
        return False

    def read(self):
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return None
        with os.fdopen(fd) as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 4096):
                raise ValueError("Unsafe web runtime information file.")
            try:
                data = json.load(handle)
            except (ValueError, UnicodeError):
                return None
        if (not isinstance(data, dict) or data.get("config") != str(self.config_path)
                or type(data.get("port")) is not int or not 1 <= data["port"] <= 65535
                or any(not isinstance(data.get(k), str) or not 20 <= len(data[k]) <= 100
                       or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                              for c in data[k])
                       for k in ("token", "instance"))):
            return None
        return data

    def write(self, app, server):
        data = {"config": str(self.config_path), "port": server.server_port,
                "token": app.owner_token, "instance": app.instance}
        temp = self.directory / (self.key + "." + secrets.token_hex(8) + ".tmp")
        try:
            fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w") as handle:
                json.dump(data, handle)
            temp.replace(self.path)
        finally:
            temp.unlink(missing_ok=True)
        return data

    def remove(self, instance=None):
        if instance is None or (data := self.read()) and data["instance"] == instance:
            self.path.unlink(missing_ok=True)


def call(data, operation, body, timeout=2):
    connection = HTTPConnection("127.0.0.1", data["port"], timeout=timeout)
    try:
        connection.request("POST", "/internal/" + operation, json.dumps(body).encode(),
                           {"Authorization": "Bearer " + data["token"],
                            "Content-Type": "application/json"})
        response = connection.getresponse()
        payload = response.read(65537)
        if response.status != 200 or len(payload) > 65536:
            raise ValueError("The local GUI server rejected the request.")
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise ValueError("Invalid GUI server response.")
        return value
    except (OSError, HTTPException):
        raise ValueError("The local GUI server is unavailable. Retry or run bibdesk-rag --web --no-browser.") from None
    finally:
        connection.close()


def alive(data):
    if data is None:
        return False
    try:
        reply = call(data, "health", {})
        return reply == {"instance": data["instance"], "config": data["config"]}
    except (OSError, ValueError, HTTPException):
        return False


def open_browser(url):
    try:
        if webbrowser.open(url, new=2):
            return
    except (OSError, webbrowser.Error):
        pass
    print("Could not launch the default browser. Open the displayed localhost URL manually.",
          file=sys.stderr)


def serve(config_path, *, port=None, no_browser=False, background=False):
    config_path = config_path.resolve()
    config = load_config(config_path)  # Pin all settings for this process.
    app = WebApp(config, config_path)
    runtime = Runtime(config_path, config)
    server = None
    lease_fd = None
    registered = False
    try:
        def register():
            nonlocal server, lease_fd
            if alive(runtime.read()):
                raise ValueError("A GUI server already uses this configuration. Use --web-open QUERY.")
            lease_fd = runtime.acquire_lease()
            server = bind_server(app, port)
            runtime.write(app, server)

        if not background:
            with runtime.lock():
                register()
        else:
            # The launcher holds the command lock while waiting for readiness.
            # The child independently acquires the lifetime lease before binding;
            # a dead launcher or two contenders still cannot create two servers.
            # No descriptor/lock inheritance across Python launchers is required.
            register()
        registered = True
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Search GUI: {url}\nPress Ctrl+C to stop.", flush=True)
        if not no_browser:
            open_browser(url)
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            print("\nSearch GUI stopped.", flush=True)
    finally:
        try:
            if server is not None:
                server.server_close()  # Wait for bounded request workers to finish.
                if registered:
                    with runtime.lock():
                        runtime.remove(app.instance)
        finally:
            if lease_fd is not None:
                os.close(lease_fd)


def launch(runtime):
    data = runtime.read()
    if alive(data):
        return data
    if runtime.lease_held():
        raise ValueError("The GUI server is busy or shutting down. Please retry shortly.")
    runtime.remove()
    child = subprocess.Popen(
        [sys.executable, "-m", "bibdesk_rag.web_runtime", str(runtime.config_path)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        data = runtime.read()
        if alive(data):
            return data
        if child.poll() is not None:
            raise ValueError("Could not start the GUI server. Run bibdesk-rag --web --no-browser for details.")
        time.sleep(0.05)
    # This is our own still-starting child, never a PID from runtime metadata.
    child.terminate()
    child.wait(timeout=5)
    raise ValueError("GUI startup timed out. Run bibdesk-rag --web --no-browser for details.")


def web_command(args):
    config_path = config_selection(args.temp)[0]
    if not config_path.is_file():
        raise ValueError("Configuration missing. Run bibdesk-rag --setup, then bibdesk-rag --index update.")
    if args.command == "web":
        serve(config_path, port=args.port, no_browser=args.no_browser)
        return 0
    config = load_config(config_path)
    # Stopping remains possible even if an index has since disappeared.
    if args.command == "web_open":
        WebApp(config, config_path)
    elif not (config.database.parent / "web-runtime").exists():
        print("Search GUI is not running for this configuration.")
        return 0
    runtime = Runtime(config_path, config)
    if args.command == "web_stop":
        with runtime.lock():
            data = runtime.read()
            if not alive(data):
                if runtime.lease_held():
                    raise ServerBusy("The GUI server is busy or shutting down. Please retry shortly.")
                runtime.remove()
                print("Search GUI is not running for this configuration.")
                return 0
            call(data, "stop", {})
        deadline = time.monotonic() + 5
        while runtime.lease_held() and time.monotonic() < deadline:
            time.sleep(.05)
        print("Search GUI shutdown requested." if runtime.lease_held() else "Search GUI stopped.")
        return 0
    with runtime.lock():
        data = launch(runtime)
        request = call(data, "initial", {"query": args.web_open})
    url = f"http://127.0.0.1:{data['port']}/#request={request['request_id']}"
    # Print only the bare URL: the one-shot request ID is transient browser data.
    print(f"Search GUI: http://127.0.0.1:{data['port']}/")
    open_browser(url)
    return 0


if __name__ == "__main__":
    # Private child entry point. Public CLI validates ports; children use an OS-assigned port.
    serve(Path(sys.argv[1]), port=0, no_browser=True, background=True)
