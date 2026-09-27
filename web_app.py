"""피터 린치 저평가 성장주 웹 관리 서버 (web_app.py)

- 로컬 HTTP 서버(포트 5055)를 실행하고 브라우저를 자동 오픈합니다.
- 최신 스크리닝 데이터 및 포트폴리오를 실시간 렌더링합니다.
"""

from __future__ import annotations

from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import sys
import threading
import time
import webbrowser

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
HTML_FILE = os.path.join(RESULTS_DIR, "peter_lynch_dashboard.html")
PORT = 5055

from dashboard_generator import generate_peter_lynch_dashboard_html


class PeterLynchWebHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ["/", "/index.html", "/dashboard"]:
            # 매 요청 시 대시보드 HTML 최신 동기화
            generate_peter_lynch_dashboard_html()
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            with open(HTML_FILE, "rb") as f:
                self.wfile.write(f.read())
        elif self.path == "/run_screening":
            from peter_lynch_screener import run_peter_lynch_screening
            run_peter_lynch_screening(limit_tickers=150)
            generate_peter_lynch_dashboard_html()
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
        else:
            super().do_GET()


def run_web_server():
    generate_peter_lynch_dashboard_html()
    os.chdir(RESULTS_DIR)
    server_address = ("127.0.0.1", PORT)
    httpd = HTTPServer(server_address, PeterLynchWebHandler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"[OK] 피터 린치 웹 대시보드 서버 가동 중: {url}")
    webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("[STOP] 서버를 종료합니다.")
        httpd.server_close()


if __name__ == "__main__":
    run_web_server()
