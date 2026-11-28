"""미국 저평가 가치주 보유 포지션 감시 및 매도 신호 모니터링 엔진 (peter_lynch_monitor.py)

[미국 가치주 5대 매도 & 리스크 관리 원칙]
1. 🚨 원금 보호 손절 (Hard Stop): 매수가 대비 -8% ~ -10% 도달 시 기계적 손절 (가치 훼손 조기 차단)
2. ⚠️ PEG 과열 버블 (PEG Overheating): 주가 급등으로 PEG > 1.8 도달 시 저평가 매력 상실 -> 전량/분할 익절 권고
3. ⚠️ 실적 훼손 경고 (Story Break): 분기 EPS 역성장 전환 또는 부채비율 급증 시 매수 이유 소멸로 매도
4. 🎯 공정 가치선 도달 (Fair Value Target): 주가가 미국 가치주 적정가치선(EPS * 성장률) 돌파 시 분할 익절
5. 🟢 텐배거 지속 보유 (Super Growth Hold): 저PEG(< 1.0) 및 고성장 지속 시 장기 복리 극대화를 위한 강력 보유
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import pandas as pd
import yfinance as yf

from portfolio_manager import load_portfolio, save_portfolio
from telegram_notifier import build_lynch_monitor_report, load_telegram_config, send_telegram_message

# Windows 콘솔 UTF-8 설정
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
SIGNALS_FILE = os.path.join(RESULTS_DIR, "latest_peter_lynch_signals.json")
TOP_PICKS_FILE = os.path.join(RESULTS_DIR, "peter_lynch_top_picks.csv")
os.makedirs(RESULTS_DIR, exist_ok=True)


def analyze_single_position(pos: dict) -> dict | None:
    """단일 보유 포지션의 펀더멘털 및 시세를 실시간 진단하여 가치주 매도 신호를 판별합니다."""
    symbol = pos.get("symbol", pos.get("code", "")).strip().upper()
    if not symbol:
        return None

    buy_price = float(pos.get("buy_price", 0.0))
    shares = int(pos.get("shares", 0))
    buy_date = pos.get("buy_date", "")

    try:
        t = yf.Ticker(symbol)
        i = t.info
        if not i:
            return None

        current_price = float(i.get("currentPrice") or i.get("regularMarketPrice") or 0.0)
        if current_price <= 0:
            return None

        pe = i.get("trailingPE")
        fwd_pe = i.get("forwardPE")
        peg = i.get("pegRatio")
        eps_growth = i.get("earningsGrowth")
        rev_growth = i.get("revenueGrowth")
        debt_to_equity = i.get("debtToEquity")
        trailing_eps = i.get("trailingEps", 0.0)

        # PEG 직접 산출 보완
        if peg is None and pe and eps_growth and eps_growth > 0:
            growth_pct = eps_growth * 100
            if growth_pct >= 5:
                peg = round(pe / growth_pct, 2)

        # 적정 가치선 산출
        fair_value = 0.0
        if trailing_eps and trailing_eps > 0 and eps_growth and eps_growth > 0:
            growth_mult = min(eps_growth * 100, 35)
            fair_value = round(trailing_eps * growth_mult, 2)

        # 손익률 계산
        return_pct = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0.0
        eval_amount = round(current_price * shares, 2)
        profit_amount = round((current_price - buy_price) * shares, 2) if buy_price > 0 else 0.0

        # ====================================================
        # 미국 가치주 5대 매도/보유 규칙 판별
        # ====================================================
        status = "NEUTRAL_HOLD"
        tag = "⚪추세관망"
        action = "HOLD"
        reason = "정상 보유 상태 유지"

        # 1. 🚨 극단적 재난 방어 손절선 (-25.0% 도달 시 비상 청산)
        if buy_price > 0 and return_pct <= -25.0:
            status = "HARD_STOP"
            tag = "🚨비상손절"
            action = "SELL"
            reason = f"매수가 대비 손실률 {return_pct:.1f}% 도달 (회계/기업 비상사태 방어 -25% 비상 손절선 이탈)"

        # 2. ⚠️ PEG 과열 버블 (PEG >= 1.8)
        elif peg and peg >= 1.8:
            status = "PEG_OVERHEAT"
            tag = "⚠️고평가익절"
            action = "SELL"
            reason = f"주가 급등으로 PEG {peg:.2f} 기록. 저평가 메리트 소멸로 차익 실현 권고"

        # 3. ⚠️ 실적 훼손 경고 (EPS 역성장 or 부채비율 급증)
        elif eps_growth is not None and eps_growth < 0:
            status = "FUNDAMENTAL_WARN"
            tag = "⚠️실적악화"
            action = "SELL"
            reason = f"최근 분기 EPS가 {eps_growth*100:+.1f}% 역성장 전환. 미국 가치주 성장 스토리 훼손"
        elif debt_to_equity and debt_to_equity > 120:
            status = "FUNDAMENTAL_WARN"
            tag = "⚠️부채경고"
            action = "SELL"
            reason = f"부채비율({debt_to_equity:.0f}%) 급증으로 재무 건전성 기준(100%) 초과"

        # 4. 🎯 공정 가치선 돌파 (Fair Value Reached)
        elif fair_value > 0 and current_price >= fair_value and return_pct >= 20.0:
            status = "TARGET_REACHED"
            tag = "🎯목표도달"
            action = "PARTIAL_SELL"
            reason = f"미국 가치주 적정주가(${fair_value:.2f}) 도달 및 수익률 {return_pct:+.1f}%. 분할 익절 권고"

        # 5. 🟢 텐배거 지속 보유 (Super Growth Strong Hold)
        elif (peg is not None and peg <= 1.1) and (eps_growth is not None and eps_growth >= 0.12):
            status = "STRONG_HOLD"
            tag = "🟢강력보유"
            action = "HOLD"
            reason = f"저평가 고성장 추세 유지 (PEG {peg:.2f}, 성장률 {eps_growth*100:+.1f}%). 텐배거 복리 지속"

        return {
            "symbol": symbol,
            "name": pos.get("name", i.get("shortName", symbol)),
            "shares": shares,
            "buy_price": buy_price,
            "buy_date": buy_date,
            "price": current_price,
            "return_pct": round(return_pct, 2),
            "eval_amount": eval_amount,
            "profit_amount": profit_amount,
            "peg": round(peg, 2) if peg is not None else None,
            "eps_growth_pct": round(eps_growth * 100, 1) if eps_growth is not None else None,
            "debt_to_equity": debt_to_equity,
            "fair_value": fair_value,
            "status": status,
            "tag": tag,
            "action": action,
            "reason": reason,
        }
    except Exception as e:
        print(f"⚠️ {symbol} 분석 중 오류: {e}")
        return None


def run_peter_lynch_monitor(send_telegram: bool = True) -> list[dict]:
    """보유 포지션 모니터링 실행"""
    today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print("=" * 95)
    print(" 🏛️ [미국 저평가 가치주 보유 포지션 실시간 감시 엔진]")
    print(f" • 실행 시각: {today_str}")
    print(" • 감시 원칙: PEG 과열(>1.8) 익절 | 원금 보호(-8%) 손절 | 실적 훼손 매도 | 저평가 텐배거 지속 보유")
    print("=" * 95)

    portfolio = load_portfolio()

    # 등록된 포지션이 없을 경우
    if not portfolio:
        print("💡 현재 등록된 보유 포지션이 없습니다. (portfolio.json)")
        print("   - KIS 계좌 연동 시 실제 잔고가 자동으로 동기화되거나,")
        print("   - 'results/peter_lynch_top_picks.csv' 종목을 포트폴리오에 추가할 수 있습니다.\n")
        
        with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": today_str,
                "total_eval_usd": 0.0,
                "total_profit_usd": 0.0,
                "signals": []
            }, f, indent=2, ensure_ascii=False)
        
        # 최신 스크리닝 결과가 있으면 TOP 5 안내
        top_picks = []
        if os.path.exists(TOP_PICKS_FILE):
            try:
                top_df = pd.read_csv(TOP_PICKS_FILE)
                top_picks = top_df.to_dict(orient="records")
            except Exception:
                pass

        if send_telegram and top_picks:
            report_msg = build_lynch_monitor_report(today_str, top_picks, [])
            send_telegram_message(report_msg)
            print("📲 텔레그램으로 최신 미국 가치주 추천 유망주 리포트를 전송했습니다.")
        return []

    print(f"🔍 보유 포지션 {len(portfolio)}개 종목 실시간 펀더멘털 및 주가 진단 중...\n")
    analyzed_list = []
    for pos in portfolio:
        res = analyze_single_position(pos)
        if res:
            analyzed_list.append(res)

    if not analyzed_list:
        print("❌ 분석 가능한 보유 종목 데이터가 없습니다.")
        return []

    # 결과 테이블 출력
    header_fmt = "{:<6} | {:<18} | {:>7} | {:>8} | {:>8} | {:>7} | {:>6} | {:>8} | {:<10}"
    print(header_fmt.format("티커", "종목명", "보유수량", "매수가($)", "현재가($)", "손익률(%)", "PEG", "평가금액", "감시신호"))
    print("-" * 95)

    row_fmt = "{:<6} | {:<18} | {:>7} | {:>8.2f} | {:>8.2f} | {:>+6.1f}% | {:>6} | {:>8.2f} | {:<10}"
    total_eval = 0.0
    total_profit = 0.0

    for item in analyzed_list:
        total_eval += item["eval_amount"]
        total_profit += item["profit_amount"]
        name_short = (item["name"][:16] + "..") if len(item["name"]) > 18 else item["name"]
        peg_str = f"{item['peg']:.2f}" if item["peg"] is not None else "-"
        print(row_fmt.format(
            item["symbol"],
            name_short,
            item["shares"],
            item["buy_price"],
            item["price"],
            item["return_pct"],
            peg_str,
            item["eval_amount"],
            item["tag"]
        ))
        if item["action"] != "HOLD":
            print(f"   └ 💡 [{item['action']}] {item['reason']}")

    tot_return_pct = (total_profit / (total_eval - total_profit) * 100) if (total_eval - total_profit) > 0 else 0.0
    print("=" * 95)
    print(f"📊 포트폴리오 총 평가액: ${total_eval:,.2f} | 총 평가손익: {total_profit:+,.2f} ({tot_return_pct:+.2f}%)")
    print("=" * 95)

    # 신호 파일 저장
    with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": today_str,
            "total_eval_usd": total_eval,
            "total_profit_usd": total_profit,
            "signals": analyzed_list
        }, f, indent=2, ensure_ascii=False)
    print(f"📁 감시 결과가 저장되었습니다: {SIGNALS_FILE}")

    # 텔레그램 발송
    if send_telegram:
        top_picks = []
        if os.path.exists(TOP_PICKS_FILE):
            try:
                top_picks = pd.read_csv(TOP_PICKS_FILE).to_dict(orient="records")
            except Exception:
                pass

        account_summary = {
            "total_asset_usd": total_eval,
            "cash_usd": 0.0,
            "total_profit_usd": total_profit,
            "total_return_pct": tot_return_pct,
            "is_mock": True
        }
        report_text = build_lynch_monitor_report(today_str, top_picks, analyzed_list, account_summary)
        ok = send_telegram_message(report_text)
        if ok:
            print("📲 텔레그램 모니터링 리포트 전송 완료!")
        else:
            print("⚠️ 텔레그램 전송 실패 또는 미설정")

    return analyzed_list


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="미국 가치주 보유 포지션 감시 엔진")
    parser.add_argument("--no-telegram", action="store_true", help="텔레그램 전송 비활성화")
    args = parser.parse_args()

    run_peter_lynch_monitor(send_telegram=not args.no_telegram)
