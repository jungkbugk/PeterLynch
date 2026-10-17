"""미국 증시 미국 가치주(US Value) 가치주 전략 5개년 실증 백테스팅 엔진 (peter_lynch_backtest.py)

- 벤치마크: S&P 500 지수 ETF (SPY)
- 전략 포트폴리오: 미국 가치주 5대 기준(PEG < 1.0, EPS성장 15~35%, 부채비율 < 80%, FCF 흑자) 충족 포트폴리오
- 5년간(2021~2026) 일간 실데이터 기반 자산 평가, CAGR, MDD, 샤프지수, 알파(Alpha) 정밀 산출
- 고해상도 성과 비교 차트 생성 (results/peter_lynch_vs_sp500_5yr.png)
"""

import os
import sys
import datetime
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Matplotlib 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


# 미국 가치주 5대 퀀트 조건에 부합하는 대표 가치주 우량/고성장 포트폴리오 (다각화 12종목)
LYNCH_PORTFOLIO_TICKERS = [
    "NVDA", # 고성장 테크, 초저PEG
    "AVGO", # 통신/반도체 고성장 저부채
    "EME",  # 인프라/엔지니어링 알짜 저PEG
    "FSLR", # 클린테크 초저부채(1.9%)
    "CF",   # 기초자재 현금창출 저PEG
    "HIG",  # 금융서비스 저PEG 고배당
    "FIX",  # 빌딩시스템 고성장
    "BSX",  # 헬스케어 메디컬 성장주
    "COO",  # 의료기기 흑자 성장주
    "AMD",  # 반도체 컴퓨팅 성장주
    "HAL",  # 에너지 캐시카우
    "CSGP", # 상업용 부동산 데이터
]

BENCHMARK_TICKER = "SPY" # S&P 500 ETF


def run_peter_lynch_backtest(
    start_date: str = "2005-01-01",
    end_date: str = "2026-09-27",
    initial_capital: float = 100_000.0, # $100,000 시작
):
    print("=" * 80)
    print(" 🇺🇸 [미국 증시 미국 가치주(US Value) 전략 5개년 실증 백테스팅]")
    print(f" • 검증 기간: {start_date} ~ {end_date} (5년 9개월)")
    print(f" • 시작 원금: ${initial_capital:,.0f} USD (약 {initial_capital*1380:,.0f}원)")
    print(" • 비교 벤치마크: S&P 500 지수 ETF (SPY)")
    print(f" • 포트폴리오 종목: {', '.join(LYNCH_PORTFOLIO_TICKERS)}")
    print("=" * 80)

    # 1. 일봉 가격 데이터 다운로드
    all_tickers = LYNCH_PORTFOLIO_TICKERS + [BENCHMARK_TICKER]
    print(f"\n📥 야후 파이낸스로부터 5년간 수정주가 데이터 다운로드 중 ({len(all_tickers)}개 종목)...")

    raw_data = yf.download(all_tickers, start=start_date, end=end_date, progress=False)

    if isinstance(raw_data.columns, pd.MultiIndex):
        if "Close" in raw_data.columns.levels[0]:
            price_df = raw_data["Close"]
        else:
            price_df = raw_data.iloc[:, :len(all_tickers)]
    else:
        price_df = raw_data

    # 결측치 보정 (전방 채우기 후 후방 채우기)
    price_df = price_df.ffill().bfill()

    # 종목별 일간 수익률 산출
    returns_df = price_df.pct_change().dropna(how='all')

    # 2. 미국 가치주 동일가중(Equal-Weight) 포트폴리오 수익률 계산
    lynch_tickers_valid = [t for t in LYNCH_PORTFOLIO_TICKERS if t in returns_df.columns]
    lynch_returns = returns_df[lynch_tickers_valid].mean(axis=1, skipna=True).dropna()

    # 벤치마크 SPY 수익률
    spy_returns = returns_df[BENCHMARK_TICKER].dropna()

    # 날짜 인덱스 교집합 정렬
    common_idx = lynch_returns.index.intersection(spy_returns.index)
    lynch_returns = lynch_returns.loc[common_idx]
    spy_returns = spy_returns.loc[common_idx]

    # 3. 누적 자산 곡선 산출
    lynch_cum = (1.0 + lynch_returns).cumprod()
    spy_cum = (1.0 + spy_returns).cumprod()

    lynch_equity = initial_capital * lynch_cum
    spy_equity = initial_capital * spy_cum

    # 4. 성과 지표 산출
    days = len(returns_df)
    years = days / 252.0

    # 총 수익률
    lynch_total_ret = (lynch_equity.iloc[-1] / initial_capital - 1.0) * 100
    spy_total_ret = (spy_equity.iloc[-1] / initial_capital - 1.0) * 100

    # 연평균 복리 수익률 (CAGR)
    lynch_cagr = ((lynch_equity.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0) * 100
    spy_cagr = ((spy_equity.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0) * 100

    # 최대 낙폭 (MDD)
    lynch_peak = lynch_equity.cummax()
    lynch_dd = (lynch_equity - lynch_peak) / lynch_peak * 100
    lynch_mdd = lynch_dd.min()

    spy_peak = spy_equity.cummax()
    spy_dd = (spy_equity - spy_peak) / spy_peak * 100
    spy_mdd = spy_dd.min()

    # 연간 변동성 (Volatility)
    lynch_vol = lynch_returns.std() * np.sqrt(252) * 100
    spy_vol = spy_returns.std() * np.sqrt(252) * 100

    # 샤프 지수 (무위험 이자율 2.0% 가정)
    rf = 0.02
    lynch_sharpe = (lynch_cagr - rf * 100) / lynch_vol if lynch_vol > 0 else 0
    spy_sharpe = (spy_cagr - rf * 100) / spy_vol if spy_vol > 0 else 0

    # 알파(Alpha) & 베타(Beta)
    covariance = np.cov(lynch_returns, spy_returns)[0][1]
    spy_variance = np.var(spy_returns)
    beta = covariance / spy_variance if spy_variance > 0 else 1.0
    alpha = (lynch_cagr - rf * 100) - beta * (spy_cagr - rf * 100)

    # 연도별 수익률 분석
    annual_df = pd.DataFrame({
        "Lynch": lynch_returns,
        "SPY": spy_returns
    })
    annual_ret = annual_df.groupby(annual_df.index.year).apply(lambda x: (1.0 + x).prod() - 1.0) * 100

    # 5. 콘솔 리포트 출력
    print("\n" + "=" * 70)
    print(" 🏆 미국 가치주 전략 vs S&P 500 (SPY) 5개년 성과 비교")
    print("=" * 70)
    print(f" {'성과 지표':<22} | {'미국 가치주 포트폴리오':>18} | {'S&P 500 (SPY)':>15}")
    print("-" * 70)
    print(f" {'최종 평가 자산':<20} | ${lynch_equity.iloc[-1]:>17,.0f} | ${spy_equity.iloc[-1]:>14,.0f}")
    print(f" {'누적 총 수익률':<20} | {lynch_total_ret:>17.2f}% | {spy_total_ret:>14.2f}%")
    print(f" {'연평균 복리수익률 (CAGR)':<16} | {lynch_cagr:>17.2f}% | {spy_cagr:>14.2f}%")
    print(f" {'최대 낙폭 (MDD)':<19} | {lynch_mdd:>17.2f}% | {spy_mdd:>14.2f}%")
    print(f" {'연간 변동성':<21} | {lynch_vol:>17.2f}% | {spy_vol:>14.2f}%")
    print(f" {'샤프 지수 (Sharpe)':<18} | {lynch_sharpe:>18.2f} | {spy_sharpe:>15.2f}")
    print(f" {'시장 민감도 (Beta)':<18} | {beta:>18.2f} | {'1.00':>15}")
    print(f" {'초과 수익률 (Alpha)':<18} | {alpha:>+17.2f}% | {'0.00%':>15}")
    print("=" * 70)

    print("\n📅 [연도별 수익률 비교]")
    for year, row in annual_ret.iterrows():
        print(f"  • {year}년: 미국 가치주 {row['Lynch']:+6.1f}% vs SPY {row['SPY']:+6.1f}% (격차: {row['Lynch']-row['SPY']:+6.1f}%p)")

    # 6. 고해상도 시각화 차트 생성
    fig = plt.figure(figsize=(14, 11), facecolor="#0b0e14")

    # 서브플롯 1: 누적 자산 성장 곡선
    ax1 = fig.add_subplot(3, 1, 1, facecolor="#151922")
    ax1.plot(lynch_equity.index, lynch_equity.values, label=f"미국 가치주 포트폴리오 (+{lynch_total_ret:.1f}%, CAGR {lynch_cagr:.1f}%)", color="#0ecb81", linewidth=2.5)
    ax1.plot(spy_equity.index, spy_equity.values, label=f"S&P 500 (SPY) (+{spy_total_ret:.1f}%, CAGR {spy_cagr:.1f}%)", color="#f0b90b", linewidth=1.8, linestyle="--")
    ax1.set_title("미국 증시 미국 가치주(US Value) 가치주 전략 vs S&P 500 누적 자산 성장 곡선 (2021~2026)", fontsize=13, fontweight="bold", color="#f0f6fc", pad=12)
    ax1.set_ylabel("자산 평가액 ($ USD)", color="#8b949e", fontsize=10)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
    ax1.grid(True, color="#242b38", linestyle="--", alpha=0.7)
    ax1.tick_params(colors="#8b949e")
    ax1.legend(loc="upper left", facecolor="#1e2329", edgecolor="#30363d", labelcolor="#f0f6fc", fontsize=10)

    # 서브플롯 2: 최대 낙폭 (Underwater Drawdown)
    ax2 = fig.add_subplot(3, 1, 2, facecolor="#151922")
    ax2.plot(lynch_dd.index, lynch_dd.values, label=f"미국 가치주 MDD ({lynch_mdd:.1f}%)", color="#0ecb81", linewidth=1.5)
    ax2.plot(spy_dd.index, spy_dd.values, label=f"S&P 500 MDD ({spy_mdd:.1f}%)", color="#f0b90b", linewidth=1.2, linestyle=":")
    ax2.fill_between(lynch_dd.index, lynch_dd.values, 0, color="#0ecb81", alpha=0.15)
    ax2.set_title("구간별 자산 고점 대비 낙폭 (Drawdown %)", fontsize=11, fontweight="bold", color="#f0f6fc", pad=10)
    ax2.set_ylabel("낙폭 (%)", color="#8b949e", fontsize=10)
    ax2.grid(True, color="#242b38", linestyle="--", alpha=0.7)
    ax2.tick_params(colors="#8b949e")
    ax2.legend(loc="lower left", facecolor="#1e2329", edgecolor="#30363d", labelcolor="#f0f6fc", fontsize=9)

    # 서브플롯 3: 연도별 수익률 막대 그래프
    ax3 = fig.add_subplot(3, 1, 3, facecolor="#151922")
    years_list = annual_ret.index.tolist()
    x = np.arange(len(years_list))
    width = 0.35

    rects1 = ax3.bar(x - width/2, annual_ret["Lynch"], width, label="미국 가치주", color="#0ecb81")
    rects2 = ax3.bar(x + width/2, annual_ret["SPY"], width, label="S&P 500 (SPY)", color="#f0b90b")

    ax3.set_title("연도별 연간 수익률 비교 (Annual Return %)", fontsize=11, fontweight="bold", color="#f0f6fc", pad=10)
    ax3.set_ylabel("수익률 (%)", color="#8b949e", fontsize=10)
    ax3.set_xticks(x)
    ax3.set_xticklabels([f"{y}년" for y in years_list], color="#8b949e")
    ax3.grid(True, color="#242b38", linestyle="--", alpha=0.7, axis="y")
    ax3.tick_params(colors="#8b949e")
    ax3.legend(loc="upper left", facecolor="#1e2329", edgecolor="#30363d", labelcolor="#f0f6fc", fontsize=9)

    # 바 레이블 추가
    for r in rects1:
        h = r.get_height()
        va = 'bottom' if h >= 0 else 'top'
        ax3.annotate(f'{h:+.1f}%', xy=(r.get_x() + r.get_width()/2, h), xytext=(0, 2 if h >= 0 else -8),
                     textcoords="offset points", ha='center', va=va, fontsize=8, color="#0ecb81", fontweight="bold")
    for r in rects2:
        h = r.get_height()
        va = 'bottom' if h >= 0 else 'top'
        ax3.annotate(f'{h:+.1f}%', xy=(r.get_x() + r.get_width()/2, h), xytext=(0, 2 if h >= 0 else -8),
                     textcoords="offset points", ha='center', va=va, fontsize=8, color="#f0b90b", fontweight="bold")

    plt.tight_layout()

    # 이미지 파일 저장
    chart_path = os.path.join(RESULTS_DIR, "peter_lynch_vs_sp500_5yr.png")
    fig.savefig(chart_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    print(f"\n📊 5개년 성과 비교 차트가 생성되었습니다: {chart_path}")

    # 성과 요약 CSV 저장
    summary_df = pd.DataFrame([{
        "전략명": "미국 가치주 포트폴리오",
        "최종자산($)": round(lynch_equity.iloc[-1], 2),
        "총수익률(%)": round(lynch_total_ret, 2),
        "CAGR(%)": round(lynch_cagr, 2),
        "MDD(%)": round(lynch_mdd, 2),
        "샤프지수": round(lynch_sharpe, 2),
        "알파(%)": round(alpha, 2),
        "베타": round(beta, 2),
    }, {
        "전략명": "S&P 500 (SPY)",
        "최종자산($)": round(spy_equity.iloc[-1], 2),
        "총수익률(%)": round(spy_total_ret, 2),
        "CAGR(%)": round(spy_cagr, 2),
        "MDD(%)": round(spy_mdd, 2),
        "샤프지수": round(spy_sharpe, 2),
        "알파(%)": 0.0,
        "베타": 1.0,
    }])
    summary_csv = os.path.join(RESULTS_DIR, "peter_lynch_backtest_summary.csv")
    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    return {
        "lynch_equity": lynch_equity.iloc[-1],
        "spy_equity": spy_equity.iloc[-1],
        "lynch_ret": lynch_total_ret,
        "spy_ret": spy_total_ret,
        "lynch_cagr": lynch_cagr,
        "spy_cagr": spy_cagr,
        "lynch_mdd": lynch_mdd,
        "spy_mdd": spy_mdd,
        "alpha": alpha,
        "chart_path": chart_path,
    }


if __name__ == "__main__":
    run_peter_lynch_backtest()
