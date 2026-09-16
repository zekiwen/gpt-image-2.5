#!/usr/bin/env python
# 草稿画板本地接收服务：纯 Python 标准库，零依赖，任意浏览器可用
#   GET  /         → 画板页面（本目录 sketch_pad.html）
#   POST /deliver  → {session, prompt, png(base64)} 直写 GPT-Image/sketch_io/<session>/
#   POST /shutdown → 画板导出成功后自动收摊：服务退出
# 必须在项目根（GPT-Image 所在目录）启动，落盘目录 = <cwd>/GPT-Image/sketch_io
import base64
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 17841
ROOT = Path.cwd()
PAD = Path(__file__).resolve().parent / "sketch_pad.html"
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        for k, v in {**CORS, "Content-Type": ctype}.items():
            self.send_header(k, v)
        if code != 204:  # 204 不允许携带 Content-Length
            self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._send(200, PAD.read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        payload = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path == "/shutdown":  # 画板导出成功后自动收摊：服务退出
            self._send(200, json.dumps({"ok": True}))
            print("[sketch-io] exported → shutdown", flush=True)
            threading.Timer(0.2, lambda: os._exit(0)).start()  # 留时间把响应送出
            return
        if self.path == "/deliver":
            try:
                data = json.loads(payload.decode("utf-8"))
                if not data.get("png"):
                    raise ValueError("missing png")
                fallback = str(int(time.time() * 1000))
                name = re.sub(r"[^\w-]", "", str(data.get("session") or fallback), flags=re.ASCII) or fallback
                d = ROOT / "GPT-Image" / "sketch_io" / name
                d.mkdir(parents=True, exist_ok=True)
                (d / "sketch.png").write_bytes(base64.b64decode(data["png"]))
                (d / "prompt.txt").write_text(str(data.get("prompt") or ""), encoding="utf-8")  # 后写：两个文件齐 = 交付完成
                self._send(200, json.dumps({"ok": True, "dir": str(d)}))
                print(f"[sketch-io] {name} → {d}", flush=True)
            except Exception as e:
                self._send(400, json.dumps({"ok": False, "error": str(e)}))
                print(f"[sketch-io] BAD {e}", file=sys.stderr, flush=True)
            return
        self._send(404, "not found", "text/plain; charset=utf-8")

    def log_message(self, *args):  # 静默逐请求访问日志，只留关键事件
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[sketch-io] http://127.0.0.1:{PORT}/  → 落盘 {ROOT / 'GPT-Image' / 'sketch_io'}", flush=True)
    server.serve_forever()
