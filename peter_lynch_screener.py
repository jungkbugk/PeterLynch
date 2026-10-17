"""미국 증시 저평가 가치주 스크리너 (peter_lynch_screener.py)

S&P 500 전종목에서 '싸면서 이익·현금흐름이 실제로 나는' 종목을 고른다.
- 적격: 순이익 > 0, 잉여현금흐름(FCF) > 0, 자기자본 > 0, 부채비율(총부채/자기자본) ≤ 100%
- 순위: 이익수익률(순이익/시가총액), FCF수익률(FCF/시가총액), 장부가/시가총액(B/P)의 순위 합 (낮을수록 저평가)
- 결과는 value_rank 순으로 results/peter_lynch_top_picks.csv 에 저장
"""

import os
import sys
import io
import time
import requests
import datetime
import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

MAX_DEBT_TO_EQUITY = 100.0   # 부채비율 상한(%)
MAX_YIELD_SANITY = 0.5       # 이익수익률/FCF수익률이 50%를 넘으면 데이터 오류로 보고 제외
FAIR_PE = 15.0               # 참고용 적정주가 = EPS × 15


def get_sp500_tickers():
    """S&P 500 전 종목 티커 수집 (위키피디아 + 백업 리스트)"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        r = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(r.text))
        df = tables[0]
        tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()
        return tickers
    except Exception as e:
        print(f"⚠ 위키피디아 S&P 500 수집 실패, 주요 우량주 리스트로 대체: {e}")
        return [
            "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "COST", "AMD",
            "QCOM", "TXN", "INTU", "AMAT", "BKNG", "LRCX", "ADI", "KLAC", "PANW", "SNPS",
            "CDNS", "CRWD", "MELI", "ANET", "FTNT", "ORCL", "CRM", "NOW", "IBM", "UBER",
            "ABBV", "LLY", "UNH", "JNJ", "MRK", "TMO", "ABT", "DHR", "ISRG", "VRTX",
            "REGN", "BSX", "SYK", "MDT", "CI", "HUM", "MCK", "COR", "IDXX", "DXCM",
            "JPM", "V", "MA", "BAC", "WFC", "MS", "GS", "SPGI", "BLK", "AXP",
            "PGR", "CB", "MMC", "AON", "AJG", "TRV", "ALL", "AFL", "MET", "PRU",
            "CAT", "GE", "UNP", "HON", "ETN", "DE", "LMT", "RTX", "BA", "GD",
            "TDG", "EMR", "PCAR", "NSC", "CSX", "PH", "CMI", "ROK", "FAST", "URI",
            "WMT", "PG", "HD", "PEP", "KO", "MCD", "NKE", "PM", "TGT", "LOW",
            "TJX", "SBUX", "MDLZ", "CL", "MO", "MNST", "KDP", "STZ", "SYY", "GIS"
        ]


def _latest(df, *names):
    """재무제표 DataFrame 에서 첫 번째로 존재하는 행의 최신 회계연도 값을 반환"""
    for n in names:
        if n in df.index:
            s = df.loc[n].dropna().sort_index(ascending=False)
            if len(s):
                return float(s.iloc[0])
    return None


def fetch_stock_value_metrics(ticker_sym: str):
    """단일 종목의 가치 지표 추출 (최근 회계연도 연간 재무 + 현재 시가총액)"""
    try:
        t = yf.Ticker(ticker_sym)
        i = t.info
        if not i:
            return None
        price = float(i.get("currentPrice") or i.get("regularMarketPrice") or 0.0)
        mcap = float(i.get("marketCap") or 0.0)
        if price <= 0 or mcap <= 0:
            return None

        inc, bal, cfs = t.income_stmt, t.balance_sheet, t.cashflow
        ni = _latest(inc, "Net Income Common Stockholders", "Net Income")
        eps = _latest(inc, "Diluted EPS", "Basic EPS")
        eq = _latest(bal, "Stockholders Equity", "Common Stock Equity")
        debt = _latest(bal, "Total Debt") or 0.0
        fcf = _latest(cfs, "Free Cash Flow")
        if fcf is None:
            ocf, capex = _latest(cfs, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities"), _latest(cfs, "Capital Expenditure")
            fcf = (ocf + (capex or 0.0)) if ocf is not None else None   # capex 는 음수로 보고됨
        if ni is None or eq is None or fcf is None:
            return None

        fair_value = eps * FAIR_PE if eps and eps > 0 else 0.0
        return {
            "symbol": ticker_sym,
            "name": i.get("shortName", ticker_sym),
            "sector": i.get("sector", "N/A"),
            "industry": i.get("industry", "N/A"),
            "price": price,
            "market_cap_b": mcap / 1e9,
            "net_income": ni,
            "equity": eq,
            "fcf": fcf,
            "debt_to_equity": (debt / eq * 100) if eq > 0 else None,
            "earnings_yield": ni / mcap,
            "fcf_yield": fcf / mcap,
            "book_to_price": eq / mcap,
            "eps": eps,
            "pe": (price / eps) if eps and eps > 0 else None,
            "fair_value": round(fair_value, 2),
            "discount_pct": round((fair_value - price) / fair_value * 100, 1) if fair_value > 0 else 0.0,
            "peg": 0.0,
            "eps_growth": 0.0,
        }
    except Exception:
        return None


def run_peter_lynch_screening(limit_tickers: int = None):
    """S&P 500 저평가 가치주 스크리닝 실행 (함수명은 기존 호출부 호환용)"""
    print("=" * 80)
    print(" 🇺🇸 [미국 증시 저평가 가치주 스크리너]")
    print(f" • 실행 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(" • 적격: 순이익>0 · FCF>0 · 자기자본>0 · 부채비율≤100%")
    print(" • 순위: 이익수익률 + FCF수익률 + 장부가/시가총액 순위 합 (낮을수록 저평가)")
    print("=" * 80)

    all_tickers = get_sp500_tickers()
    if limit_tickers and limit_tickers < len(all_tickers) and limit_tickers < 400:
        import random
        target_tickers = random.Random(datetime.date.today().toordinal()).sample(all_tickers, limit_tickers)
    else:
        target_tickers = all_tickers

    print(f"\n🔍 {len(target_tickers)}개 종목 재무제표 멀티스레드 수집 중...")
    start_t = time.time()
    data_list = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(fetch_stock_value_metrics, sym): sym for sym in target_tickers}
        completed = 0
        for f in as_completed(futures):
            res = f.result()
            if res:
                data_list.append(res)
            completed += 1
            if completed % 100 == 0 or completed == len(target_tickers):
                print(f"  진행률: {completed}/{len(target_tickers)} ({completed/len(target_tickers)*100:.1f}%)")
    print(f"✅ {len(data_list)}개 종목 데이터 수집 완료 ({time.time()-start_t:.1f}초)\n")

    df = pd.DataFrame(data_list)
    if df.empty:
        print("❌ 수집된 종목이 없습니다.")
        return df

    eligible = df[
        (df["net_income"] > 0) & (df["fcf"] > 0) & (df["equity"] > 0) &
        (df["debt_to_equity"].notnull()) & (df["debt_to_equity"] <= MAX_DEBT_TO_EQUITY) &
        (df["earnings_yield"] <= MAX_YIELD_SANITY) & (df["fcf_yield"] <= MAX_YIELD_SANITY)
    ].copy()

    # 순위 합산 (수익률이 높을수록 저평가 → 순위 1)
    eligible["value_score"] = (
        eligible["earnings_yield"].rank(ascending=False) +
        eligible["fcf_yield"].rank(ascending=False) +
        eligible["book_to_price"].rank(ascending=False)
    )
    top_picks = eligible.sort_values(by=["value_score", "fcf_yield"], ascending=[True, False]).reset_index(drop=True)
    top_picks["value_rank"] = top_picks.index + 1
    top_picks["lynch_score"] = top_picks["value_score"]      # 기존 컬럼 호환

    csv_path = os.path.join(RESULTS_DIR, "peter_lynch_top_picks.csv")
    top_picks.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print("=" * 100)
    print(f" 🏆 저평가 가치주 TOP 20 (적격 {len(top_picks)}개 / 수집 {len(df)}개)")
    print("=" * 100)
    print("{:<3} {:<6} {:<24} {:<18} {:>9} {:>8} {:>8} {:>8} {:>7}".format("순위", "티커", "기업명", "섹터", "현재가($)", "E/P", "FCF/P", "B/P", "부채%"))
    for _, r in top_picks.head(20).iterrows():
        print("{:<3} {:<6} {:<24} {:<18} {:>9.2f} {:>7.1%} {:>7.1%} {:>7.2f} {:>7.0f}".format(
            int(r["value_rank"]), r["symbol"], str(r["name"])[:22], str(r["sector"])[:16], r["price"],
            r["earnings_yield"], r["fcf_yield"], r["book_to_price"], r["debt_to_equity"]))
    print("=" * 100)
    print(f"📁 상세 데이터가 저장되었습니다: {csv_path}\n")
    return top_picks


# 기존 코드 호환 별칭
fetch_stock_lynch_metrics = fetch_stock_value_metrics


if __name__ == "__main__":
    run_peter_lynch_screening()
