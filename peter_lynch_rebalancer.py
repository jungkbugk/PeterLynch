"""피터 린치 저평가 고성장주 미국주식 자동 매수 & 포트폴리오 리밸런싱 엔진 (peter_lynch_rebalancer.py)

지원 기능:
1. 최신 피터 린치 TOP N(기본 10~12개) 저평가 고성장주 자동 선정
2. 한국투자증권(KIS) 미국주식 계좌 실시간 잔고 및 보유 포지션 조회
3. 균등 비중(Equal Weight) 목표 배분 및 탈락 종목 매도 / 신규 종목 매수 수량 자동 산출
4. 🧪 안전 가상 시뮬레이션(Dry-Run) 및 ⚡ 실전/모의 주문 즉시 집행 지원
5. 텔레그램 리밸런싱 완료 보고서 자동 전송
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import pandas as pd
import yfinance as yf

from kis_us_api import KisUsClient
from portfolio_manager import load_portfolio, save_portfolio, sync_portfolio_from_kis
from peter_lynch_screener import run_peter_lynch_screening
from telegram_notifier import build_lynch_rebalance_report, send_telegram_message

# Windows 콘솔 UTF-8 설정
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
TOP_PICKS_FILE = os.path.join(RESULTS_DIR, "peter_lynch_top_picks.csv")
REBALANCE_LOG_FILE = os.path.join(RESULTS_DIR, "latest_rebalance_plan.json")


def get_current_price(symbol: str) -> float:
    """단일 종목의 실시간 현재가 조회"""
    try:
        t = yf.Ticker(symbol)
        p = float(t.info.get("currentPrice") or t.info.get("regularMarketPrice") or 0.0)
        if p > 0:
            return round(p, 2)
    except Exception:
        pass
    return 0.0


def plan_lynch_rebalancing(
    target_count: int = 10,
    capital_override: float | None = None,
    client: KisUsClient | None = None
) -> dict:
    """피터 린치 원칙에 따른 리밸런싱 주문 계획을 수립합니다."""
    if client is None:
        client = KisUsClient()

    # 1. 최신 스크리너 결과 확인 (없으면 자동 실행)
    if not os.path.exists(TOP_PICKS_FILE):
        print("🔍 최신 스크리닝 데이터가 없어 피터 린치 스크리너를 즉시 실행합니다...")
        run_peter_lynch_screening(limit_tickers=200)

    top_df = pd.read_csv(TOP_PICKS_FILE)
    top_candidates = top_df.head(target_count).to_dict(orient="records")
    top_symbols = [c["symbol"].upper() for c in top_candidates]

    # 2. 계좌 잔고 및 보유 종목 조회
    bal = client.get_us_balance()
    is_virtual = bal.get("is_virtual_fallback", False)
    total_asset = bal["total_asset_usd"]
    cash_available = bal["cash_usd"]

    # 예수금이 0이거나 가상 테스트 자본 지정 시
    if capital_override and capital_override > 0:
        total_asset = capital_override
        cash_available = capital_override
        is_virtual = True
    elif total_asset <= 0:
        # 모의계좌에 잔고가 아직 입금되지 않은 경우 기본 시뮬레이션 자본 $20,000 책정
        total_asset = 20000.0
        cash_available = 20000.0
        is_virtual = True

    holdings = bal.get("holdings", [])
    # KIS 잔고가 비어있다면 로컬 portfolio.json 참조
    if not holdings:
        local_p = load_portfolio()
        for p in local_p:
            sym = p.get("symbol", p.get("code", "")).upper()
            curr_p = get_current_price(sym) or p.get("buy_price", 0.0)
            holdings.append({
                "symbol": sym,
                "shares": p.get("shares", 0),
                "buy_price": p.get("buy_price", 0.0),
                "current_price": curr_p,
                "eval_amount": curr_p * p.get("shares", 0),
                "name": p.get("name", sym)
            })

    current_holding_map = {h["symbol"].upper(): h for h in holdings if h["shares"] > 0}

    # 3. 목표 자산 배분 (종목당 동일 비중)
    target_equity_per_stock = total_asset / target_count
    orders = []

    # 단계 A: 탈락 종목 전량 매도 (기존 보유 종목 중 린치 상위권에서 탈락한 종목)
    for sym, h in current_holding_map.items():
        if sym not in top_symbols:
            curr_p = h["current_price"] or get_current_price(sym)
            if curr_p > 0 and h["shares"] > 0:
                orders.append({
                    "action": "SELL",
                    "side": "SELL",
                    "symbol": sym,
                    "name": h.get("name", sym),
                    "current_shares": h["shares"],
                    "target_shares": 0,
                    "qty": h["shares"],
                    "price": curr_p,
                    "amount": round(curr_p * h["shares"], 2),
                    "reason": "피터린치 유망주 순위 탈락 또는 조건 미달",
                })
                cash_available += curr_p * h["shares"]

    # 단계 B: 목표 유망주 리밸런싱 및 신규 매수
    for c in top_candidates:
        sym = c["symbol"].upper()
        curr_p = float(c["price"])
        if curr_p <= 0:
            curr_p = get_current_price(sym)
        if curr_p <= 0:
            continue

        target_shares = int(target_equity_per_stock / curr_p)
        curr_shares = current_holding_map.get(sym, {}).get("shares", 0)
        diff_shares = target_shares - curr_shares

        # 매수/매도 주문 필요성 판단 (최소 1주 이상 차이날 때)
        if diff_shares > 0:
            order_cost = round(diff_shares * curr_p, 2)
            orders.append({
                "action": "BUY",
                "side": "BUY",
                "symbol": sym,
                "name": c.get("name", sym),
                "current_shares": curr_shares,
                "target_shares": target_shares,
                "qty": diff_shares,
                "price": curr_p,
                "amount": order_cost,
                "reason": "신규 편입" if curr_shares == 0 else "비중 확대(균등 리밸런싱)",
            })
        elif diff_shares < -1:  # 비중이 과도하게 초과된 경우 부분 차익실현
            sell_qty = abs(diff_shares)
            order_proceeds = round(sell_qty * curr_p, 2)
            orders.append({
                "action": "SELL",
                "side": "SELL",
                "symbol": sym,
                "name": c.get("name", sym),
                "current_shares": curr_shares,
                "target_shares": target_shares,
                "qty": sell_qty,
                "price": curr_p,
                "amount": order_proceeds,
                "reason": "비중 축소(초과 수익 차익 실현)",
            })

    # 정렬: 매도 주문 우선, 그 후 매수 주문
    orders.sort(key=lambda x: (0 if x["side"] == "SELL" else 1, x["symbol"]))

    return {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "account_no": bal["account_no"],
        "is_mock": bal["is_mock"],
        "is_virtual": is_virtual,
        "total_asset": round(total_asset, 2),
        "total_asset_usd": round(total_asset, 2),
        "cash_available": round(cash_available, 2),
        "target_count": target_count,
        "target_equity_per_stock": round(target_equity_per_stock, 2),
        "orders": orders,
        "top_candidates": top_candidates
    }



def trigger_peter_lynch_dashboard_sync():
    """모바일 대시보드(GitHub Pages) 비동기 동기화"""
    import threading
    import subprocess
    def _worker():
        try:
            CREATE_NO_WINDOW = 0x08000000
            subprocess.run(
                [sys.executable, "dashboard_generator.py"],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                creationflags=CREATE_NO_WINDOW
            )
            subprocess.run(
                [sys.executable, "sync_to_github.py"],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                creationflags=CREATE_NO_WINDOW
            )
            print("[웹 대시보드] 📱 스마트폰 모바일 대시보드(GitHub Pages) 실시간 동기화 완료!")
        except Exception as e:
            print(f"[웹 대시보드 동기화 오류] {e}")
    threading.Thread(target=_worker, daemon=True).start()


def execute_rebalancing(
    plan: dict,
    is_dry_run: bool = True,
    client: KisUsClient | None = None,
    send_telegram: bool = True
) -> dict:
    """리밸런싱 주문을 실제로 실행하거나 가상 시뮬레이션을 수행합니다."""
    if client is None:
        client = KisUsClient()

    orders = plan["orders"]
    total_asset = plan["total_asset"]

    print("=" * 95)
    mode_str = "🧪 [가상 시뮬레이션 모드 (DRY-RUN)]" if is_dry_run else "⚡ [실제 주문 집행 모드 (EXECUTE)]"
    print(f" {mode_str} 피터 린치 포트폴리오 리밸런싱")
    print(f" • 계좌: {plan['account_no']} ({'모의투자' if plan['is_mock'] else '실전계좌'})")
    print(f" • 총 운용 자산: ${total_asset:,.2f} | 목표 종목 수: {plan['target_count']}개 (종목당 ~${plan['target_equity_per_stock']:,.2f})")
    print("=" * 95)

    if not orders:
        print("✅ 모든 보유 종목이 목표 균등 비중과 완벽히 일치하여 실행할 주문이 없습니다.\n")
        return {"success": True, "results": [], "plan": plan}

    # 주문 명세서 테이블 출력
    header_fmt = "{:<5} | {:<6} | {:<20} | {:>6} -> {:>6} | {:>5}주 | {:>8} | {:>9} | {:<16}"
    print(header_fmt.format("구분", "티커", "종목명", "현재", "목표", "주문수량", "단가($)", "주문총액($)", "사유"))
    print("-" * 95)

    row_fmt = "{:<5} | {:<6} | {:<20} | {:>6} -> {:>6} | {:>5}주 | {:>8.2f} | {:>9.2f} | {:<16}"
    total_buy_amt = 0.0
    total_sell_amt = 0.0

    for o in orders:
        if o["side"] == "BUY":
            total_buy_amt += o["amount"]
        else:
            total_sell_amt += o["amount"]

        name_short = (o["name"][:18] + "..") if len(o["name"]) > 20 else o["name"]
        print(row_fmt.format(
            "🔵매수" if o["side"] == "BUY" else "🔴매도",
            o["symbol"],
            name_short,
            o["current_shares"],
            o["target_shares"],
            o["qty"],
            o["price"],
            o["amount"],
            o["reason"]
        ))

    print("-" * 95)
    print(f"💰 총 매도 예정액: ${total_sell_amt:,.2f} | 총 매수 예정액: ${total_buy_amt:,.2f}")
    cash_left = total_asset + total_sell_amt - total_buy_amt
    print(f"💵 예상 잔여 현금: ${cash_left:,.2f}")
    print("=" * 95)

    # 실제 주문 처리
    results = []
    new_portfolio_positions = []

    if not is_dry_run:
        # 🛡️ 안전장치: 실제 외화(USD) 가용 구매력(현재 현금 + 매도 예정액) 확인
        real_bal = client.get_us_balance()
        real_cash = real_bal.get("cash_usd", 0.0)
        available_purchasing_power = real_cash + total_sell_amt
        if available_purchasing_power < total_buy_amt * 0.95 and not real_bal.get("is_virtual_fallback"):
            print(f"\n❌ [안전장치 차단] 가용 구매력(${available_purchasing_power:,.2f} = 예수금 ${real_cash:,.2f} + 매도대금 ${total_sell_amt:,.2f})이 매수 필요 금액(${total_buy_amt:,.2f})보다 부족합니다.")
            print("💡 한국투자증권 앱(MTS)에서 원화를 외화(USD)로 환전하시거나 매수 규모를 조정해주세요.")
            return {"success": False, "msg": "외화 예수금 부족으로 주문 취소", "plan": plan}

        print("\n🚀 [KIS API 미국 주식 주문 전송 시작]...")
        for o in orders:
            res = client.order_us_stock(
                symbol=o["symbol"],
                qty=o["qty"],
                price=o["price"],
                side=o["side"],
                order_type="00",
                dry_run=False
            )
            results.append(res)
            status_icon = "✅" if res.get("success") else "❌"
            print(f" {status_icon} {o['side']} {o['symbol']} x {o['qty']}주 @ ${o['price']:.2f} -> {res.get('msg')}")

        # 포트폴리오 JSON 갱신 (기존 보유 종목의 평단가 가중치 및 매수일자 보존)
        old_portfolio = {p.get("symbol", p.get("code", "")).upper(): p for p in load_portfolio()}
        for c in plan["top_candidates"]:
            sym = c["symbol"].upper()
            target_sh = int(plan["target_equity_per_stock"] / float(c["price"]))
            if target_sh > 0:
                p_curr = float(c["price"])
                old_p = old_portfolio.get(sym)
                if old_p and old_p.get("shares", 0) > 0:
                    old_sh = old_p.get("shares", 0)
                    old_bp = float(old_p.get("buy_price", p_curr))
                    # 가중 평균 단가
                    if target_sh > old_sh:
                        add_sh = target_sh - old_sh
                        new_bp = round((old_sh * old_bp + add_sh * p_curr) / target_sh, 2)
                    else:
                        new_bp = old_bp
                    buy_date = old_p.get("buy_date", datetime.datetime.now().strftime("%Y-%m-%d"))
                else:
                    new_bp = p_curr
                    buy_date = datetime.datetime.now().strftime("%Y-%m-%d")

                new_portfolio_positions.append({
                    "symbol": sym,
                    "code": sym,
                    "name": c.get("name", sym),
                    "market": "US",
                    "shares": target_sh,
                    "buy_price": new_bp,
                    "buy_date": buy_date,
                    "initial_peg": c.get("peg"),
                    "fair_value": c.get("fair_value"),
                    "memo": "피터 린치 자동 리밸런싱"
                })
        save_portfolio(new_portfolio_positions)
        print("💾 portfolio.json 포트폴리오 내역이 성공적으로 갱신되었습니다.")
        trigger_peter_lynch_dashboard_sync()

    else:
        # Dry-run 시뮬레이션
        for o in orders:
            res = client.order_us_stock(
                symbol=o["symbol"],
                qty=o["qty"],
                price=o["price"],
                side=o["side"],
                order_type="00",
                dry_run=True
            )
            results.append(res)
        print("💡 [안내] 위 내용은 가상 시뮬레이션입니다. 실제 주문을 넣으려면 '--execute' 옵션을 사용하세요.")

    # 계획 파일 저장
    plan["execution_results"] = results
    with open(REBALANCE_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

    # 텔레그램 알림 전송
    if send_telegram:
        msg = build_lynch_rebalance_report(orders, total_asset, cash_left, is_dry_run=is_dry_run)
        send_telegram_message(msg)
        print("📲 리밸런싱 보고서가 텔레그램으로 전송되었습니다.")

    return {"success": True, "results": results, "plan": plan}


def main():
    parser = argparse.ArgumentParser(description="피터 린치 포트폴리오 자동 리밸런싱 도구")
    parser.add_argument("--count", type=int, default=10, help="목표 균등 분산 종목 수 (기본: 10개)")
    parser.add_argument("--capital", type=float, default=None, help="시뮬레이션 운용 자산 설정 ($)")
    parser.add_argument("--execute", action="store_true", help="실제 주문 집행 (기본값은 안전 가상 시뮬레이션)")
    parser.add_argument("--no-telegram", action="store_true", help="텔레그램 알림 전송 비활성화")
    parser.add_argument("--yes", action="store_true", help="실제 주문 시 확인 절차 생략")
    args = parser.parse_args()

    client = KisUsClient()
    plan = plan_lynch_rebalancing(target_count=args.count, capital_override=args.capital, client=client)

    is_dry_run = not args.execute
    if args.execute and not args.yes:
        print("\n⚠️ 주의: 실제 증권사 계좌로 미국주식 주문이 전송됩니다!")
        ans = input("계속 진행하시겠습니까? (yes/N): ").strip().lower()
        if ans != "yes":
            print("취소되었습니다. 가상 시뮬레이션(Dry-Run) 모드로 실행합니다.")
            is_dry_run = True

    execute_rebalancing(plan, is_dry_run=is_dry_run, client=client, send_telegram=not args.no_telegram)


if __name__ == "__main__":
    main()
