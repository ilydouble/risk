"""Fixed container launcher. Only this internal service has Docker daemon access."""

import hmac
import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

IMAGE = os.environ.get("PREPARATION_RUNTIME_IMAGE", "risk-data-prep-runtime:local")
TOKEN = os.environ["PREPARATION_RUNNER_TOKEN"]
SLOT = threading.BoundedSemaphore(1)
MAX_BODY = 100 * 1024**2
CATALOG = None
CATALOG_LOCK = threading.Lock()


def launch(body=None):
    image = subprocess.check_output(
        ["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE], timeout=15,
    ).decode().strip()
    name = "risk-preparation-" + uuid4().hex
    command = ["docker", "run", "--name", name, "--rm", "-i", "--network", "none",
               "--read-only", "--cap-drop", "ALL", "--cap-add", "SETUID", "--cap-add", "SETGID",
               "--cap-add", "KILL",
               "--security-opt", "no-new-privileges", "--pids-limit", "128", "--memory", "2g",
               "--memory-swap", "2g", "--cpus", "2", "--ulimit", "nofile=256:256",
               "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m,mode=1777",
               "--tmpfs", "/work:rw,noexec,nosuid,size=768m,mode=755", image]
    if body is None:
        command.append("--catalog")
    else:
        body["runtimeImage"] = image
    try:
        result = subprocess.run(command, input=json.dumps(body).encode() if body else b"",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=190)
        if result.returncode:
            raise RuntimeError("隔离容器启动失败，请检查执行器镜像与Docker配置")
        data = json.loads(result.stdout)
        data["runtimeImage"] = image
        return data
    finally:
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=20)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + TOKEN):
            self.send_error(401)
            return
        if self.path not in {"/catalog", "/run"}:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_BODY:
            self.send_error(413)
            return
        running = self.path == "/run"
        if running and not SLOT.acquire(blocking=False):
            self.send_error(503)
            return
        try:
            body = json.loads(self.rfile.read(length))
            if running:
                data = launch(body)
            else:
                global CATALOG
                with CATALOG_LOCK:
                    if CATALOG is None:
                        CATALOG = launch()
                    data = CATALOG
            encoded = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except Exception:
            self.send_error(503, "Preparation executor unavailable")
        finally:
            if running:
                SLOT.release()

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8090), Handler).serve_forever()
