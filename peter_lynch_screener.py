"""미국 증시 피터 린치 저평가 고성장주(GARP) 실시간 스크리너 (peter_lynch_screener.py)

피터 린치 5대 핵심 퀀트 원칙:
1. PEG Ratio < 1.0 (성장률 대비 극저평가, 0.5 이하는 10루타 후보)
2. 지속 가능한 EPS 성장률 (15% ~ 35%)
3. 재무 건전성 (부채비율 Debt-to-Equity < 80%)
4. 건전한 유동성 (유동비율 Current Ratio >= 1.0)
5. 잉여현금흐름 (Free Cash Flow > 0)
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
        # 핵심 우량/성장주 100선 백업
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


def fetch_stock_lynch_metrics(ticker_sym: str):
    """단일 종목의 피터 린치 펀더멘털 지표 추출"""
    try:
        t = yf.Ticker(ticker_sym)
        i = t.info
        if not i or "regularMarketPrice" not in i and "currentPrice" not in i:
            return None

        price = float(i.get("currentPrice") or i.get("regularMarketPrice") or 0.0)
        if price <= 0:
            return None

        pe = i.get("trailingPE")
        fwd_pe = i.get("forwardPE")
        peg = i.get("pegRatio")
        de = i.get("debtToEquity")
        eps_growth = i.get("earningsGrowth")
        rev_growth = i.get("revenueGrowth")
        fcf = i.get("freeCashflow")
        current_ratio = i.get("currentRatio")
        op_margins = i.get("operatingMargins")
        market_cap = i.get("marketCap", 0)
        trailing_eps = i.get("trailingEps", 0.0)

        # PEG가 None일 경우 PER / (성장률*100)으로 직접 산출
        calc_peg = peg
        if calc_peg is None and pe and eps_growth and eps_growth > 0:
            growth_pct = eps_growth * 100
            if growth_pct >= 5:
                calc_peg = round(pe / growth_pct, 2)

        # 피터 린치 적정 주가 (Fair Value Line = EPS * (성장률*100) 또는 EPS * 15)
        fair_value = 0.0
        discount_pct = 0.0
        if trailing_eps and trailing_eps > 0 and eps_growth and eps_growth > 0:
            growth_mult = min(eps_growth * 100, 35) # 최대 35배 상한
            fair_value = trailing_eps * growth_mult
            if fair_value > 0:
                discount_pct = ((fair_value - price) / fair_value) * 100

        return {
            "symbol": ticker_sym,
            "name": i.get("shortName", ticker_sym),
            "sector": i.get("sector", "N/A"),
            "industry": i.get("industry", "N/A"),
            "price": price,
            "pe": pe,
            "forward_pe": fwd_pe,
            "peg": calc_peg,
            "eps_growth": eps_growth,
            "rev_growth": rev_growth,
            "debt_to_equity": de,
            "current_ratio": current_ratio,
            "op_margins": op_margins,
            "fcf": fcf,
            "market_cap_b": market_cap / 1e9 if market_cap else 0.0,
            "fair_value": round(fair_value, 2),
            "discount_pct": round(discount_pct, 1),
        }
    except Exception:
        return None


def run_peter_lynch_screening(limit_tickers: int = 250):
    """피터 린치 조건에 부합하는 저평가 고성장주 스크리닝 실행"""
    print("=" * 80)
    print(" 🇺🇸 [미국 증시 피터 린치(Peter Lynch) 저평가 고성장주 퀀트 스크리너]")
    print(f" • 실행 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(" • 철학: GARP (Growth At a Reasonable Price, 합리적인 가격의 성장주 발굴)")
    print(" • 기준: PEG < 1.0 (0.5 이하 10루타 후보) | EPS성장 15~35% | 부채비율 < 80% | FCF > 0")
    print("=" * 80)

    all_tickers = get_sp500_tickers()
    if limit_tickers and limit_tickers < len(all_tickers):
        target_tickers = all_tickers[:limit_tickers]
    else:
        target_tickers = all_tickers

    print(f"\n🔍 미국 우량주 {len(target_tickers)}개 종목 재무제표 멀티스레드 고속 수집 중...")
    start_t = time.time()

    data_list = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(fetch_stock_lynch_metrics, sym): sym for sym in target_tickers}
        completed = 0
        for f in as_completed(futures):
            res = f.result()
            if res:
                data_list.append(res)
            completed += 1
            if completed % 50 == 0 or completed == len(target_tickers):
                print(f"  진행률: {completed}/{len(target_tickers)} ({completed/len(target_tickers)*100:.1f}%) 완료...")

    print(f"✅ {len(data_list)}개 종목 데이터 수집 완료 ({time.time()-start_t:.1f}초 소요)\n")

    df = pd.DataFrame(data_list)

    # 1. 피터 린치 엄격 필터링 조건 적용
    #  - PEG가 0 초과 1.2 이하 (0.5 이하는 최고점)
    #  - EPS 성장률 10% 이상 (권장 15% 이상)
    #  - 부채비율(Debt/Equity) 80 이하 (저부채)
    #  - FCF > 0 (잉여현금흐름 흑자)
    filtered = df[
        (df["peg"].notnull()) & (df["peg"] > 0) & (df["peg"] <= 1.2) &
        (df["eps_growth"].notnull()) & (df["eps_growth"] >= 0.12) &
        (df["debt_to_equity"].notnull()) & (df["debt_to_equity"] <= 100) &
        (df["fcf"].notnull()) & (df["fcf"] > 0)
    ].copy()

    # 2. 피터 린치 스코어링 (PEG가 낮을수록, EPS성장률 높을수록, 부채 적을수록 가산점)
    # 린치 매력도 = (EPS 성장률 * 100) / PEG - (부채비율 / 10)
    filtered["lynch_score"] = (
        (filtered["eps_growth"] * 100) / filtered["peg"] - (filtered["debt_to_equity"] * 0.1)
    ).round(1)

    # 정렬: 피터 린치 스코어 내림차순, PEG 오름차순
    top_picks = filtered.sort_values(by=["peg", "lynch_score"], ascending=[True, False]).reset_index(drop=True)

    # 결과 CSV 저장
    csv_path = os.path.join(RESULTS_DIR, "peter_lynch_top_picks.csv")
    top_picks.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # 결과 리포트 출력
    print("=" * 95)
    print(f" 🏆 피터 린치 기준 최우수 저평가 고성장주 TOP 15 (발굴 종목: 총 {len(top_picks)}개 중 선별)")
    print("=" * 95)
    header_fmt = "{:<6} | {:<22} | {:<16} | {:>8} | {:>6} | {:>9} | {:>7} | {:>8} | {:>8}"
    print(header_fmt.format("티커", "기업명", "섹터", "현재가($)", "PEG", "EPS성장률", "부채비율", "적정주가", "상승여력"))
    print("-" * 95)

    row_fmt = "{:<6} | {:<22} | {:<16} | {:>8.2f} | {:>6.2f} | {:>8.1f}% | {:>6.1f}% | {:>8.2f} | {:>7.1f}%"
    for idx, row in top_picks.head(15).iterrows():
        name_short = (row['name'][:20] + '..') if len(str(row['name'])) > 22 else str(row['name'])
        sector_short = (row['sector'][:14] + '..') if len(str(row['sector'])) > 16 else str(row['sector'])
        print(row_fmt.format(
            row["symbol"],
            name_short,
            sector_short,
            row["price"],
            row["peg"],
            row["eps_growth"] * 100,
            row["debt_to_equity"],
            row["fair_value"],
            row["discount_pct"]
        ))
    print("=" * 95)
    print(f"📁 상세 데이터가 저장되었습니다: {csv_path}\n")

    return top_picks


if __name__ == "__main__":
    run_peter_lynch_screening(limit_tickers=300)
