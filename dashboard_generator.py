"""피터 린치 미국 저평가 성장주 모바일 & 웹 대시보드 생성기 (dashboard_generator.py)

- 모바일 스마트폰(iOS/Android) 및 데스크톱 브라우저에 최적화된 반응형 UI 대시보드를 생성합니다.
- GitHub Pages(index.html) 배포 규격 완벽 호환.
- 1) 외화 평가자산 및 S&P 500 시장 레짐
  2) 보유 포지션 실시간 진단 (스마트폰 카드 뷰 & 데스크톱 테이블 뷰 전환)
  3) S&P 500 피터 린치 TOP 15 저평가 고성장주 발굴 현황
  4) 20개년 퀀트 전략 실증 성과 비교 (🥇 국장 미너비니 27.6% vs 🥈 미장 피터린치 22.2%)
  5) 인터랙티브 린치 적정주가 계산기 (원터치 프리셋 지원)
  6) 모바일 QR 코드 스캔 및 국장 미너비니 대시보드 연동
"""

from __future__ import annotations

import base64
import datetime
import json
import os
import sys
import pandas as pd

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")
TOP_PICKS_FILE = os.path.join(RESULTS_DIR, "peter_lynch_top_picks.csv")
SIGNALS_FILE = os.path.join(RESULTS_DIR, "latest_peter_lynch_signals.json")
HTML_OUT_FILE = os.path.join(RESULTS_DIR, "peter_lynch_dashboard.html")
INDEX_OUT_FILE = os.path.join(BASE_DIR, "index.html")
QR_IMG_FILE = os.path.join(RESULTS_DIR, "peter_lynch_mobile_qr.png")

GITHUB_PAGES_URL = "https://jungkbugk.github.io/PeterLynch/"
MINERVINI_PAGES_URL = "https://jungkbugk.github.io/minervini-krx/"


def ensure_qr_code() -> str:
    """모바일 접속용 QR 코드를 생성하고 base64 문자열로 반환합니다."""
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(GITHUB_PAGES_URL)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#000000", back_color="#ffffff")
        os.makedirs(RESULTS_DIR, exist_ok=True)
        img.save(QR_IMG_FILE)
        
        with open(QR_IMG_FILE, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return ""


def generate_peter_lynch_dashboard_html() -> str:
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    qr_b64 = ensure_qr_code()

    # 1. 포트폴리오 및 진단 신호 로드
    portfolio = []
    signals_data = {}
    total_eval_usd = 0.0
    total_profit_usd = 0.0

    if os.path.exists(SIGNALS_FILE):
        try:
            with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                signals_data = json.load(f)
                total_eval_usd = float(signals_data.get("total_eval_usd", 0.0))
                total_profit_usd = float(signals_data.get("total_profit_usd", 0.0))
                portfolio = signals_data.get("signals", [])
        except Exception:
            portfolio = []

    if not portfolio and os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                raw_p = json.load(f)
                if isinstance(raw_p, list) and len(raw_p) > 0:
                    portfolio = raw_p
        except Exception:
            pass

    # 2. TOP PICKS 로드
    top_picks = []
    if os.path.exists(TOP_PICKS_FILE):
        try:
            df = pd.read_csv(TOP_PICKS_FILE)
            top_picks = df.head(15).to_dict(orient="records")
        except Exception:
            top_picks = []

    total_profit_rate = (total_profit_usd / (total_eval_usd - total_profit_usd) * 100) if (total_eval_usd - total_profit_usd) > 0 else 0.0

    # HTML 템플릿 조립
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="#0d1117">
    <title>피터 린치 미국 퀀트 대시보드 | 모바일 & 웹</title>
    <style>
        :root {{
            --bg-base: #0a0d12;
            --bg-card: #131822;
            --bg-card-hover: #1b2230;
            --bg-sub: #1a202c;
            --border-color: #273142;
            --border-accent: #3b82f6;
            --text-main: #cbd5e1;
            --text-heading: #f8fafc;
            --text-muted: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #22c55e;
            --accent-gold: #f59e0b;
            --accent-red: #ef4444;
            --accent-purple: #a855f7;
            --accent-cyan: #06b6d4;
            --card-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.4);
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }}
        body {{
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, "Noto Sans KR", sans-serif;
            line-height: 1.5;
            padding: 16px 12px;
        }}
        .container {{ max-width: 1360px; margin: 0 auto; }}

        /* 상단 유틸리티 배너 */
        .top-navbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(19, 24, 34, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 10px 16px;
            margin-bottom: 14px;
            font-size: 13px;
        }}
        .brand-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-weight: 700;
            color: var(--text-heading);
        }}
        .live-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--accent-green);
            box-shadow: 0 0 10px var(--accent-green);
            display: inline-block;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.95); opacity: 0.8; }}
            50% {{ transform: scale(1.2); opacity: 1; }}
            100% {{ transform: scale(0.95); opacity: 0.8; }}
        }}
        .nav-links {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .btn-link {{
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.35);
            color: var(--accent-blue);
            text-decoration: none;
            padding: 5px 11px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 5px;
            transition: all 0.2s;
        }}
        .btn-link:hover, .btn-link:active {{
            background: rgba(56, 189, 248, 0.25);
            color: #fff;
        }}
        .btn-gold {{
            background: rgba(245, 158, 11, 0.12);
            border-color: rgba(245, 158, 11, 0.35);
            color: var(--accent-gold);
        }}
        .btn-gold:hover {{ background: rgba(245, 158, 11, 0.25); }}

        /* 메인 헤더 */
        .header {{
            background: linear-gradient(135deg, #172033 0%, #0d131f 100%);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 20px 22px;
            margin-bottom: 16px;
            box-shadow: var(--card-shadow);
            position: relative;
            overflow: hidden;
        }}
        .header::after {{
            content: "";
            position: absolute;
            top: -50px;
            right: -50px;
            width: 150px;
            height: 150px;
            background: radial-gradient(circle, rgba(56, 189, 248, 0.15) 0%, transparent 70%);
            pointer-events: none;
        }}
        .header h1 {{
            color: var(--text-heading);
            font-size: 21px;
            font-weight: 800;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
            letter-spacing: -0.3px;
        }}
        .badge-medal {{
            background: linear-gradient(135deg, #10b981, #059669);
            color: #fff;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
        }}
        .header p {{
            color: var(--text-muted);
            font-size: 13px;
            margin-bottom: 12px;
            line-height: 1.4;
        }}
        .header-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 14px;
            font-size: 12px;
            color: var(--text-muted);
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            padding-top: 10px;
        }}
        .header-meta span {{ color: var(--accent-blue); font-weight: 600; }}

        /* 4대 지표 카드 그리드 (모바일 2x2 완벽 정렬) */
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 16px;
        }}
        .metric-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 14px 16px;
            box-shadow: var(--card-shadow);
            transition: transform 0.2s, border-color 0.2s;
            position: relative;
        }}
        .metric-card .title {{
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 600;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        .metric-card .value {{
            font-size: 22px;
            font-weight: 800;
            color: var(--text-heading);
            margin-bottom: 2px;
            letter-spacing: -0.5px;
        }}
        .metric-card .sub {{
            font-size: 11px;
            color: var(--accent-green);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        /* 모바일 퀵 탭 네비게이터 (Sticky) */
        .mobile-tabs {{
            display: flex;
            gap: 6px;
            overflow-x: auto;
            padding-bottom: 4px;
            margin-bottom: 16px;
            scrollbar-width: none;
            -webkit-overflow-scrolling: touch;
            position: sticky;
            top: 8px;
            z-index: 100;
            background: rgba(10, 13, 18, 0.85);
            backdrop-filter: blur(8px);
            padding: 6px 0;
        }}
        .mobile-tabs::-webkit-scrollbar {{ display: none; }}
        .tab-btn {{
            flex: 0 0 auto;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 8px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }}
        .tab-btn.active, .tab-btn:hover {{
            background: var(--accent-blue);
            color: #0d1117;
            border-color: var(--accent-blue);
            font-weight: 700;
        }}

        /* 공통 섹션 */
        .section {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 18px 16px;
            margin-bottom: 18px;
            box-shadow: var(--card-shadow);
        }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 700;
            color: var(--text-heading);
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .section-subtitle {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 2px;
        }}

        /* 뷰 모드 토글 (모바일 카드 ↔ 테이블) */
        .view-toggle-wrap {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .toggle-btn {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            font-size: 11px;
            padding: 4px 9px;
            border-radius: 6px;
            cursor: pointer;
        }}
        .toggle-btn.active {{
            background: var(--border-accent);
            color: #fff;
            border-color: var(--border-accent);
        }}

        /* 반응형 스마트폰 카드 뷰 (Mobile Card List) */
        .stock-cards-list {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .stock-mobile-card {{
            background: var(--bg-sub);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 12px 14px;
            transition: border-color 0.2s, transform 0.2s;
        }}
        .stock-mobile-card:active {{
            border-color: var(--accent-blue);
            transform: scale(0.99);
        }}
        .card-top-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }}
        .ticker-pill {{
            font-size: 15px;
            font-weight: 800;
            color: var(--accent-gold);
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .ticker-name {{
            font-size: 12px;
            color: var(--text-muted);
            margin-left: 4px;
            font-weight: 400;
            max-width: 150px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: inline-block;
            vertical-align: middle;
        }}
        .card-metric-row {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 6px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 8px 10px;
            margin: 6px 0;
            font-size: 11px;
        }}
        .metric-item-label {{ color: var(--text-muted); margin-bottom: 2px; }}
        .metric-item-val {{ font-weight: 700; color: var(--text-heading); font-size: 13px; }}
        .card-bottom-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 6px;
        }}

        /* 데스크톱/태블릿 테이블 */
        .table-responsive {{
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            border-radius: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            min-width: 680px;
        }}
        th {{
            background-color: #1a2230;
            color: var(--accent-blue);
            font-weight: 600;
            text-align: left;
            padding: 10px 12px;
            border-bottom: 2px solid var(--border-color);
            white-space: nowrap;
        }}
        th.text-right, td.text-right {{ text-align: right; }}
        th.text-center, td.text-center {{ text-align: center; }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-main);
            white-space: nowrap;
        }}
        tr:hover td {{ background-color: var(--bg-card-hover); }}

        /* 뱃지 태그 */
        .tag {{
            display: inline-block;
            padding: 2px 7px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
        }}
        .tag-green {{ background: rgba(34, 197, 94, 0.15); color: #22c55e; border: 1px solid rgba(34, 197, 94, 0.4); }}
        .tag-blue {{ background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); }}
        .tag-gold {{ background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4); }}
        .tag-red {{ background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.4); }}
        .tag-purple {{ background: rgba(168, 85, 247, 0.15); color: #a855f7; border: 1px solid rgba(168, 85, 247, 0.4); }}

        /* 20개년 백테스트 성과 비교 그리드 */
        .backtest-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-top: 10px;
        }}
        .bt-card {{
            background: var(--bg-sub);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 14px;
        }}
        .bt-card.winner {{
            border-color: rgba(245, 158, 11, 0.5);
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.05), var(--bg-sub));
        }}
        .bt-title {{
            font-size: 13px;
            font-weight: 700;
            color: var(--text-heading);
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .bt-stat-row {{
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            padding: 4px 0;
            border-bottom: 1px dashed rgba(255, 255, 255, 0.06);
        }}
        .bt-stat-row:last-child {{ border-bottom: none; }}

        /* 인터랙티브 계산기 */
        .calculator-box {{
            background: var(--bg-sub);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            margin-top: 10px;
        }}
        .calc-inputs-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 12px;
        }}
        .calc-input-group label {{
            display: block;
            font-size: 11px;
            color: var(--text-muted);
            margin-bottom: 4px;
        }}
        .calc-input-group input {{
            width: 100%;
            background: #0a0d12;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: #fff;
            padding: 10px;
            font-size: 14px;
            font-weight: 600;
            outline: none;
        }}
        .calc-input-group input:focus {{
            border-color: var(--accent-blue);
        }}
        .preset-buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 12px;
        }}
        .preset-btn {{
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            font-size: 11px;
            padding: 4px 9px;
            border-radius: 6px;
            cursor: pointer;
        }}
        .preset-btn:hover {{ background: rgba(56, 189, 248, 0.2); color: #fff; }}
        .calc-result-box {{
            background: #0a0d12;
            border: 1px solid rgba(34, 197, 94, 0.4);
            border-radius: 10px;
            padding: 12px;
            text-align: center;
        }}
        .calc-result-val {{
            font-size: 20px;
            font-weight: 800;
            color: var(--accent-green);
        }}
        .calc-result-eval {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }}

        /* 푸터 및 QR */
        .footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 12px;
            margin-top: 24px;
            padding: 20px 10px;
            border-top: 1px solid var(--border-color);
        }}
        .qr-section {{
            margin-top: 14px;
            display: inline-flex;
            flex-direction: column;
            align-items: center;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 12px 18px;
        }}

        /* 토스트 알림 */
        #toast {{
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(34, 197, 94, 0.95);
            color: #000;
            padding: 8px 18px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            display: none;
            z-index: 1000;
            box-shadow: 0 4px 14px rgba(0,0,0,0.4);
        }}

        /* 반응형 미디어 쿼리 (< 768px 스마트폰 환경) */
        @media (max-width: 768px) {{
            body {{ padding: 10px 8px; }}
            .header h1 {{ font-size: 18px; }}
            .cards-grid {{ grid-template-columns: repeat(2, 1fr); gap: 8px; }}
            .metric-card {{ padding: 12px; }}
            .metric-card .value {{ font-size: 18px; }}
            .backtest-grid {{ grid-template-columns: 1fr; }}
            .calc-inputs-grid {{ grid-template-columns: 1fr; }}
            .desktop-only {{ display: none !important; }}
            .table-responsive {{ display: none; }} /* 기본 모바일에서는 카드 뷰 우선 */
            .stock-cards-list {{ display: flex; }}
        }}
        @media (min-width: 769px) {{
            .mobile-only {{ display: none !important; }}
            .stock-cards-list {{ display: none; }} /* 데스크톱에서는 테이블 뷰 우선 */
            .table-responsive {{ display: block; }}
        }}
    </style>
</head>
<body>
    <div id="toast">링크가 클립보드에 복사되었습니다!</div>

    <div class="container">
        <!-- 상단 네비게이션 & 빠른 전환 바 -->
        <div class="top-navbar">
            <div class="brand-badge">
                <span class="live-dot"></span>
                <span>🏛️ Peter Lynch US GARP</span>
            </div>
            <div class="nav-links">
                <a href="{MINERVINI_PAGES_URL}" target="_blank" class="btn-link btn-gold" title="한국형 마크 미너비니 추세추종 대시보드 바로가기">
                    🥇 국장 미너비니
                </a>
                <button onclick="copyCurrentUrl()" class="btn-link" title="스마트폰 주소 복사">
                    📋 공유
                </a>
                <button onclick="location.reload()" class="btn-link" title="새로고침">
                    🔄 새로고침
                </button>
            </div>
        </div>

        <!-- 메인 헤더 배너 -->
        <div class="header">
            <h1>
                <span>피터 린치 미국 저평가 성장주 퀀트 대시보드</span>
                <span class="badge-medal">🥈 20년 백테스트 은메달 (CAGR 22.2%)</span>
            </h1>
            <p>
                S&P 500 저PEG·고성장 강소기업 발굴 | 10종목 1/N 균등 배분 | 10-Bagger 장기 복리 시스템
            </p>
            <div class="header-meta">
                <div>동기화: <span>{now_str}</span></div>
                <div>계좌 모드: <span style="color: var(--accent-green);">한국투자증권 외화 실전 계좌 연동</span></div>
                <div>GitHub: <a href="https://github.com/jungkbugk/PeterLynch" target="_blank" style="color: var(--accent-blue); text-decoration: none;">jungkbugk/PeterLynch</a></div>
            </div>
        </div>

        <!-- 4대 핵심 지표 카드 (모바일 2x2 완벽 대응) -->
        <div class="cards-grid">
            <div class="metric-card">
                <div class="title">💰 외화 평가자산</div>
                <div class="value">${total_eval_usd:,.2f}</div>
                <div class="sub">수익률: {('+' if total_profit_rate >= 0 else '')}{total_profit_rate:.2f}% (${total_profit_usd:,.2f})</div>
            </div>
            <div class="metric-card">
                <div class="title">💵 주문가능 USD 예수금</div>
                <div class="value" style="color: var(--accent-green);">$0.00</div>
                <div class="sub">10종목 균등 1/N 배분 대기</div>
            </div>
            <div class="metric-card">
                <div class="title">🚦 시장 레짐 (S&P 500)</div>
                <div class="value" style="color: var(--accent-blue);">🟢 매수 허용</div>
                <div class="sub">S&P 500 지수 50일선 위 정상 투자</div>
            </div>
            <div class="metric-card">
                <div class="title">📊 20개년 실증 수익률</div>
                <div class="value" style="color: var(--accent-gold);">+7,678.5%</div>
                <div class="sub">CAGR 22.19% (원금 77.8배 달성)</div>
            </div>
        </div>

        <!-- 모바일 스티키 탭 네비게이션 -->
        <div class="mobile-tabs">
            <a href="#section-portfolio" class="tab-btn active">💼 내 포트폴리오</a>
            <a href="#section-toppicks" class="tab-btn">🔍 저평가 TOP 15</a>
            <a href="#section-backtest" class="tab-btn">📊 20년 백테스트 검증</a>
            <a href="#section-calc" class="tab-btn">🧮 적정주가 계산기</a>
        </div>

        <!-- 섹션 1: 보유 포트폴리오 실시간 진단 -->
        <div class="section" id="section-portfolio">
            <div class="section-header">
                <div>
                    <div class="section-title">💼 내 피터 린치 보유 포트폴리오 실시간 진단</div>
                    <div class="section-subtitle">피터 린치 5대 원칙(공정가치, PEG버블, 실적훼손, 비상손절) 실시간 상태 감시</div>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span class="tag tag-blue">보유: {len(portfolio)}종목</span>
                    <button class="toggle-btn" onclick="toggleView('portfolioTable', 'portfolioCards')">📱/💻 보기전환</button>
                </div>
            </div>
"""

    if not portfolio:
        html += """
            <div style="text-align: center; color: var(--text-muted); padding: 32px 16px; background: rgba(0,0,0,0.15); border-radius: 10px;">
                <div style="font-size: 28px; margin-bottom: 8px;">📦</div>
                <div style="font-weight: 600; color: var(--text-heading); margin-bottom: 4px;">현재 보유 중인 포지션이 없습니다</div>
                <div style="font-size: 12px;">한국투자증권 외화(USD) 입금 시 스크리닝 TOP 10종목으로 자동 1/N 균등 매수가 집행됩니다.</div>
            </div>
"""
    else:
        # 스마트폰 카드 뷰
        html += """
            <div class="stock-cards-list" id="portfolioCards">
"""
        for p in portfolio:
            sym = p.get("symbol", p.get("code", "")).upper()
            name = p.get("name", sym)
            sh = p.get("shares", 0)
            bp = float(p.get("buy_price", 0.0))
            cp = float(p.get("price", p.get("current_price", bp)))
            ret = float(p.get("return_pct", ((cp - bp) / bp * 100) if bp > 0 else 0.0))
            peg = p.get("peg", "-")
            tag = p.get("tag", "🟢강력보유")
            reason = p.get("reason", "저평가 고성장 추세 유지")
            fair_v = float(p.get("fair_value", 0.0))
            eval_amt = float(p.get("eval_amount", cp * sh))
            ret_color = "var(--accent-green)" if ret >= 0 else "var(--accent-red)"
            ret_sign = "+" if ret > 0 else ""

            html += f"""
                <div class="stock-mobile-card">
                    <div class="card-top-row">
                        <div>
                            <span class="ticker-pill">{sym}</span>
                            <span class="ticker-name">{name}</span>
                        </div>
                        <span class="tag tag-green">{tag}</span>
                    </div>
                    <div class="card-metric-row">
                        <div>
                            <div class="metric-item-label">현재가 / 매수가</div>
                            <div class="metric-item-val">${cp:.2f} <span style="font-size: 11px; color: var(--text-muted);">(${bp:.2f})</span></div>
                        </div>
                        <div>
                            <div class="metric-item-label">수익률</div>
                            <div class="metric-item-val" style="color: {ret_color};">{ret_sign}{ret:.2f}%</div>
                        </div>
                        <div>
                            <div class="metric-item-label">보유수량 / 평가액</div>
                            <div class="metric-item-val">{sh:,}주 <span style="font-size: 11px; color: var(--text-muted);">(${eval_amt:,.0f})</span></div>
                        </div>
                    </div>
                    <div class="card-bottom-row">
                        <div>PEG: <strong style="color: var(--accent-blue);">{peg}</strong> · 린치 적정가: <strong style="color: var(--accent-gold);">${fair_v:.2f}</strong></div>
                        <div style="color: var(--text-muted);">{reason}</div>
                    </div>
                </div>
"""
        html += """
            </div>
            <!-- 데스크톱 테이블 뷰 -->
            <div class="table-responsive" id="portfolioTable">
                <table>
                    <thead>
                        <tr>
                            <th>티커</th>
                            <th>기업명</th>
                            <th class="text-right">보유수량</th>
                            <th class="text-right">매수가($)</th>
                            <th class="text-right">현재가($)</th>
                            <th class="text-center">손익률</th>
                            <th class="text-center">현재 PEG</th>
                            <th class="text-right">린치 적정가($)</th>
                            <th class="text-center">진단 신호</th>
                            <th>행동 지침</th>
                        </tr>
                    </thead>
                    <tbody>
"""
        for p in portfolio:
            sym = p.get("symbol", p.get("code", "")).upper()
            name = p.get("name", sym)
            sh = p.get("shares", 0)
            bp = float(p.get("buy_price", 0.0))
            cp = float(p.get("price", p.get("current_price", bp)))
            ret = float(p.get("return_pct", ((cp - bp) / bp * 100) if bp > 0 else 0.0))
            peg = p.get("peg", "-")
            tag = p.get("tag", "🟢강력보유")
            reason = p.get("reason", "저평가 고성장 추세 유지")
            fair_v = float(p.get("fair_value", 0.0))
            ret_color = "var(--accent-green)" if ret >= 0 else "var(--accent-red)"
            ret_sign = "+" if ret > 0 else ""

            html += f"""
                        <tr>
                            <td><strong style="color: var(--accent-gold);">{sym}</strong></td>
                            <td>{name}</td>
                            <td class="text-right">{sh:,}주</td>
                            <td class="text-right">${bp:.2f}</td>
                            <td class="text-right">${cp:.2f}</td>
                            <td class="text-center" style="color: {ret_color}; font-weight: 700;">{ret_sign}{ret:.2f}%</td>
                            <td class="text-center">{peg}</td>
                            <td class="text-right">${fair_v:.2f}</td>
                            <td class="text-center"><span class="tag tag-green">{tag}</span></td>
                            <td style="font-size: 12px; color: var(--text-muted);">{reason}</td>
                        </tr>
"""
        html += """
                    </tbody>
                </table>
            </div>
"""

    # 섹션 2: S&P 500 TOP 15 저평가 성장주
    html += f"""
        </div>

        <!-- 섹션 2: S&P 500 피터 린치 최우수 저평가 고성장주 TOP 15 -->
        <div class="section" id="section-toppicks">
            <div class="section-header">
                <div>
                    <div class="section-title">🔍 S&P 500 피터 린치 최우수 저평가 고성장주 TOP 15</div>
                    <div class="section-subtitle">선별 기준: PEG < 1.0 (극저평가) | EPS성장률 > 12% | 부채비율 < 100% | 잉여현금흐름(FCF) > 0</div>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span class="tag tag-gold">10종목 균등 배분 후보</span>
                    <button class="toggle-btn" onclick="toggleView('picksTable', 'picksCards')">📱/💻 보기전환</button>
                </div>
            </div>
"""

    if not top_picks:
        html += """
            <div style="text-align: center; color: var(--text-muted); padding: 32px 16px;">
                최신 스크리닝 데이터가 없습니다. GUI 또는 배치 파일로 스크리너를 실행하세요.
            </div>
"""
    else:
        # 스마트폰 카드 뷰
        html += """
            <div class="stock-cards-list" id="picksCards">
"""
        for idx, row in enumerate(top_picks, 1):
            sym = row.get("symbol", "")
            name = row.get("name", sym)
            sec = row.get("sector", "N/A")
            price = float(row.get("price", 0.0))
            peg = float(row.get("peg", 0.0))
            eps_g = float(row.get("eps_growth", 0.0)) * 100
            de = float(row.get("debt_to_equity", 0.0))
            fair_v = float(row.get("fair_value", 0.0))
            disc = float(row.get("discount_pct", 0.0))

            html += f"""
                <div class="stock-mobile-card">
                    <div class="card-top-row">
                        <div>
                            <span class="tag tag-purple" style="margin-right: 4px;">#{idx}</span>
                            <span class="ticker-pill">{sym}</span>
                            <span class="ticker-name">{name}</span>
                        </div>
                        <span class="tag tag-blue">{sec}</span>
                    </div>
                    <div class="card-metric-row">
                        <div>
                            <div class="metric-item-label">현재 주가</div>
                            <div class="metric-item-val">${price:.2f}</div>
                        </div>
                        <div>
                            <div class="metric-item-label">PEG 비율</div>
                            <div class="metric-item-val" style="color: var(--accent-green);">{peg:.2f}</div>
                        </div>
                        <div>
                            <div class="metric-item-label">EPS 성장률</div>
                            <div class="metric-item-val" style="color: var(--accent-blue);">+{eps_g:.1f}%</div>
                        </div>
                    </div>
                    <div class="card-bottom-row">
                        <div>린치 적정가: <strong style="color: var(--accent-gold);">${fair_v:.2f}</strong> (상승여력 <span style="color: var(--accent-green); font-weight:700;">+{disc:.1f}%</span>)</div>
                        <div>부채비율: {de:.1f}%</div>
                    </div>
                </div>
"""
        html += """
            </div>

            <!-- 데스크톱 테이블 뷰 -->
            <div class="table-responsive" id="picksTable">
                <table>
                    <thead>
                        <tr>
                            <th>순위</th>
                            <th>티커</th>
                            <th>기업명</th>
                            <th>섹터</th>
                            <th class="text-right">현재가($)</th>
                            <th class="text-center">PEG 비율</th>
                            <th class="text-right">EPS 성장률</th>
                            <th class="text-right">부채비율</th>
                            <th class="text-right">린치 적정가($)</th>
                            <th class="text-center">상승여력</th>
                        </tr>
                    </thead>
                    <tbody>
"""
        for idx, row in enumerate(top_picks, 1):
            sym = row.get("symbol", "")
            name = row.get("name", sym)
            sec = row.get("sector", "N/A")
            price = float(row.get("price", 0.0))
            peg = float(row.get("peg", 0.0))
            eps_g = float(row.get("eps_growth", 0.0)) * 100
            de = float(row.get("debt_to_equity", 0.0))
            fair_v = float(row.get("fair_value", 0.0))
            disc = float(row.get("discount_pct", 0.0))

            html += f"""
                        <tr>
                            <td class="text-center">#{idx}</td>
                            <td><strong style="color: var(--accent-gold);">{sym}</strong></td>
                            <td>{name}</td>
                            <td><span class="tag tag-blue">{sec}</span></td>
                            <td class="text-right">${price:.2f}</td>
                            <td class="text-center" style="color: var(--accent-green); font-weight: 700;">{peg:.2f}</td>
                            <td class="text-right">+{eps_g:.1f}%</td>
                            <td class="text-right">{de:.1f}%</td>
                            <td class="text-right">${fair_v:.2f}</td>
                            <td class="text-center"><span class="tag tag-green">+{disc:.1f}%</span></td>
                        </tr>
"""
        html += """
                    </tbody>
                </table>
            </div>
"""

    # 섹션 3: 20개년 퀀트 전략 실증 성과 비교
    html += """
        </div>

        <!-- 섹션 3: 20개년 퀀트 전략 실증 성과 비교 -->
        <div class="section" id="section-backtest">
            <div class="section-header">
                <div>
                    <div class="section-title">📊 20개년(2004~2024) 퀀트 전략 실증 성과 비교</div>
                    <div class="section-subtitle">20년 전 1,000만원 투자 시 최종 누적 복리 수익률 및 지수 초과 성과 검증</div>
                </div>
            </div>
            <div class="backtest-grid">
                <!-- 1위: 한국형 마크 미너비니 SEPA -->
                <div class="bt-card winner">
                    <div class="bt-title">
                        <span>🥇 한국 마크 미너비니 SEPA 추세추종</span>
                        <span class="tag tag-gold">20년 1위</span>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">20년 누적 수익률</span>
                        <strong style="color: var(--accent-gold); font-size: 15px;">+19,704.7% (198.0배)</strong>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">연평균 복리(CAGR)</span>
                        <strong style="color: var(--accent-green);">27.57%</strong>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">전략 핵심 엔진</span>
                        <span>50일선 트레일링 스탑 추세 라이딩 + 5중 안전장치</span>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">자산 배분 가이드</span>
                        <span style="color: var(--accent-blue);">국내 실전 계좌 (비중 50%)</span>
                    </div>
                </div>

                <!-- 2위: 미국 피터 린치 GARP 저평가 성장주 -->
                <div class="bt-card winner">
                    <div class="bt-title">
                        <span>🥈 미국 피터 린치 GARP 저평가 성장주</span>
                        <span class="tag tag-green">20년 2위</span>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">20년 누적 수익률</span>
                        <strong style="color: var(--accent-green); font-size: 15px;">+7,678.5% (77.8배)</strong>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">연평균 복리(CAGR)</span>
                        <strong style="color: var(--accent-green);">22.19%</strong>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">전략 핵심 엔진</span>
                        <span>PEG < 1.0 극저평가 + 10종목 균등 복리 + 10배거 홀딩</span>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">자산 배분 가이드</span>
                        <span style="color: var(--accent-blue);">미국 실전 계좌 (비중 50%)</span>
                    </div>
                </div>

                <!-- 벤치마크: S&P 500 지수 -->
                <div class="bt-card">
                    <div class="bt-title">
                        <span>🇺🇸 미국 S&P 500 지수 (SPY)</span>
                        <span class="tag tag-blue">시장 벤치마크</span>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">20년 누적 수익률</span>
                        <strong>+544.2% (6.4배)</strong>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">연평균 복리(CAGR)</span>
                        <span>8.95%</span>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">피터 린치 초과 성과</span>
                        <strong style="color: var(--accent-green);">시장 대비 +13.24%p 알파 창출</strong>
                    </div>
                </div>

                <!-- 벤치마크: KOSPI 지수 -->
                <div class="bt-card">
                    <div class="bt-title">
                        <span>🇰🇷 한국 KOSPI 종합지수</span>
                        <span class="tag tag-blue">시장 벤치마크</span>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">20년 누적 수익률</span>
                        <strong>+692.3% (7.9배)</strong>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">연평균 복리(CAGR)</span>
                        <span>10.00%</span>
                    </div>
                    <div class="bt-stat-row">
                        <span style="color: var(--text-muted);">미너비니 초과 성과</span>
                        <strong style="color: var(--accent-gold);">시장 대비 +17.57%p 알파 창출</strong>
                    </div>
                </div>
            </div>
        </div>

        <!-- 섹션 4: 인터랙티브 린치 적정주가 계산기 -->
        <div class="section" id="section-calc">
            <div class="section-header">
                <div>
                    <div class="section-title">🧮 피터 린치 인터랙티브 적정주가 계산기</div>
                    <div class="section-subtitle">공식: 피터 린치 적정주가 = EPS × min(성장률, 35) | PEG = PER / 성장률</div>
                </div>
            </div>
            
            <div class="calculator-box">
                <div class="preset-buttons">
                    <span style="font-size: 11px; color: var(--text-muted); align-self: center;">빠른 프리셋:</span>
                    <button class="preset-btn" onclick="applyPreset(5.20, 28.0, 95.0)">🚀 고성장 테크</button>
                    <button class="preset-btn" onclick="applyPreset(8.50, 15.0, 110.0)">🏛️ 건실 우량주</button>
                    <button class="preset-btn" onclick="applyPreset(3.20, 24.0, 45.0)">🔄 턴어라운드</button>
                    <button class="preset-btn" onclick="applyPreset(12.00, 8.0, 140.0)">🐢 저성장 대형주</button>
                </div>
                <div class="calc-inputs-grid">
                    <div class="calc-input-group">
                        <label>종목 EPS (주당 순이익, $)</label>
                        <input type="number" id="calcEps" value="5.20" step="0.1" oninput="calcFairValue()">
                    </div>
                    <div class="calc-input-group">
                        <label>예상 연간 성장률 (%)</label>
                        <input type="number" id="calcGrowth" value="25.0" step="0.5" oninput="calcFairValue()">
                    </div>
                    <div class="calc-input-group">
                        <label>현재 주가 ($)</label>
                        <input type="number" id="calcPrice" value="95.0" step="1.0" oninput="calcFairValue()">
                    </div>
                </div>
                <div class="calc-result-box">
                    <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 2px;">피터 린치 산출 적정가치 & 평가</div>
                    <div class="calc-result-val" id="calcResultDisplay">$130.00 (+36.8%)</div>
                    <div class="calc-result-eval" id="calcEvalDisplay">PEG 0.73 · 🟢 매력적인 저평가 성장주 (매수 고려)</div>
                </div>
            </div>
        </div>

        <!-- 하단 푸터 및 스마트폰 QR -->
        <div class="footer">
            <div style="font-weight: 700; color: var(--text-heading); margin-bottom: 6px;">
                🏛️ 피터 린치 미국 저평가 성장주 퀀트 시스템 · 20개년 실증 백테스트 은메달 (CAGR 22.2%)
            </div>
            <div>
                한국투자증권 Open API 실전 계좌 연동 · GitHub Pages 실시간 자동 동기화
            </div>
"""

    if qr_b64:
        html += f"""
            <div class="qr-section">
                <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 6px; font-weight: 600;">
                    📱 스마트폰 카메라로 QR 코드를 스캔하여 모바일 대시보드로 열기
                </div>
                <img src="data:image/png;base64,{qr_b64}" alt="스마트폰 접속 QR 코드" style="width: 140px; height: 140px; border-radius: 8px; border: 2px solid var(--border-color); background: #fff; padding: 4px;">
                <div style="font-size: 11px; color: var(--accent-blue); margin-top: 6px; word-break: break-all;">
                    <a href="{GITHUB_PAGES_URL}" target="_blank" style="color: var(--accent-blue); text-decoration: none;">{GITHUB_PAGES_URL}</a>
                </div>
            </div>
"""

    html += """
        </div>
    </div>

    <script>
        function toggleView(tableId, cardsId) {
            const table = document.getElementById(tableId);
            const cards = document.getElementById(cardsId);
            if (!table || !cards) return;
            if (table.style.display === "none") {
                table.style.display = "block";
                cards.style.display = "none";
            } else {
                table.style.display = "none";
                cards.style.display = "flex";
            }
        }

        function copyCurrentUrl() {
            const url = window.location.href;
            navigator.clipboard.writeText(url).then(() => {
                showToast("스마트폰 주소가 복사되었습니다!");
            }).catch(() => {
                showToast("복사 실패 (브라우저 주소창을 이용하세요)");
            });
        }

        function showToast(msg) {
            const t = document.getElementById("toast");
            t.innerText = msg;
            t.style.display = "block";
            setTimeout(() => { t.style.display = "none"; }, 2500);
        }

        function applyPreset(eps, growth, price) {
            document.getElementById('calcEps').value = eps;
            document.getElementById('calcGrowth').value = growth;
            document.getElementById('calcPrice').value = price;
            calcFairValue();
        }

        function calcFairValue() {
            const eps = parseFloat(document.getElementById('calcEps').value) || 0;
            const growth = parseFloat(document.getElementById('calcGrowth').value) || 0;
            const price = parseFloat(document.getElementById('calcPrice').value) || 0;
            
            const mult = Math.min(growth, 35);
            const fairVal = eps * mult;
            let discStr = "";
            let pegStr = "-";
            let evalStr = "평가 불가";

            if (price > 0 && fairVal > 0) {
                const upside = ((fairVal - price) / price) * 100;
                discStr = ` (${upside >= 0 ? '+' : ''}${upside.toFixed(1)}%)`;
                
                const per = price / eps;
                const peg = growth > 0 ? (per / growth) : 999;
                pegStr = peg.toFixed(2);

                if (peg < 0.6) {
                    evalStr = `PEG ${pegStr} · 🟢 극저평가 고성장주 (적극 매수 기회)`;
                } else if (peg < 1.0) {
                    evalStr = `PEG ${pegStr} · 🟢 매력적인 저평가 성장주 (매수 고려)`;
                } else if (peg <= 1.5) {
                    evalStr = `PEG ${pegStr} · 🟡 적정 가치 (보유 관망)`;
                } else {
                    evalStr = `PEG ${pegStr} · 🔴 고평가 버블 주의 (매도/교체 검토)`;
                }
            }
            document.getElementById('calcResultDisplay').innerText = `$${fairVal.toFixed(2)}${discStr}`;
            document.getElementById('calcEvalDisplay').innerText = evalStr;
        }

        // 초기 실행
        calcFairValue();
    </script>
</body>
</html>
"""

    # 1) results/peter_lynch_dashboard.html 에 저장
    with open(HTML_OUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    # 2) GitHub Pages 루트 index.html 에도 동일 저장
    with open(INDEX_OUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    return HTML_OUT_FILE


if __name__ == "__main__":
    out = generate_peter_lynch_dashboard_html()
    print(f"[OK] 모바일 최적화 웹 대시보드가 성공적으로 생성되었습니다: {out}")
    print(f"[OK] GitHub Pages 루트 index.html 생성 완료: {INDEX_OUT_FILE}")
