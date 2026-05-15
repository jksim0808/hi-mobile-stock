import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from ta.momentum import RSIIndicator
from ta.trend import MACD


def analyze_momentum(ticker_list):
    results = []

    print(f"\n{'종목코드':<10} | {'현재가':<10} | {'RSI':<6} | {'상태':<10}")
    print("-" * 50)


    for ticker in ticker_list:
        try:
            # [수정] auto_adjust=True를 추가하고 데이터를 단순화합니다.
            data = yf.download(ticker, period="100d", interval="1d", progress=False, auto_adjust=True)
            if data.empty: continue

            # [핵심 수정] 멀티 인덱스를 제거하여 단일 종목 데이터로 변환합니다.
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # 데이터가 Series 형태일 경우를 대비해 숫자로 확실히 추출
            curr_price = float(data['Close'].iloc[-1])

            # 나머지 지표 계산은 동일하게 진행
            data['MA5'] = data['Close'].rolling(window=5).mean()
            data['MA20'] = data['Close'].rolling(window=20).mean()
            data['MA60'] = data['Close'].rolling(window=60).mean()

           # RSI (14일)
            rsi_int = RSIIndicator(close=data['Close'].squeeze(), window=14)
            data['RSI'] = rsi_int.rsi()

            # 거래량 이평선 (20일 평균 대비 현재 거래량)
            avg_volume = data['Volume'].rolling(window=20).mean().iloc[-1]
            curr_volume = data['Volume'].iloc[-1]

            # 3. 모멘텀 판별 로직
            curr_price = float(data['Close'].iloc[-1])
            curr_rsi = float(data['RSI'].iloc[-1])

            # 조건 A: 정배열 (5 > 20 > 60)
            is_trending = data['MA5'].iloc[-1] > data['MA20'].iloc[-1] > data['MA60'].iloc[-1]
            # 조건 B: 거래량 폭발 (평균 대비 1.5배 이상)
            is_vol_spike = curr_volume > avg_volume * 1.5
            # 조건 C: RSI가 50~70 사이 (상승 탄력이 붙었으나 과매수는 아닌 상태)
            is_good_rsi = 50 < curr_rsi < 70

            status = "대기"
            if is_trending and is_good_rsi:
                status = "★매수추천★"
                if is_vol_spike: status = "★★강력매수★★"

                results.append({
                    'ticker': ticker,
                    'data': data,
                    'status': status
                })

            print(f"{ticker:<10} | {curr_price:<12,.0f} | {curr_rsi:<8.2f} | {status}")

        except Exception as e:
            print(f"{ticker} 분석 중 오류 발생: {e}")

    return results


def plot_momentum(ticker, data):
    """추천 종목의 차트를 시각화합니다."""
    plt.figure(figsize=(12, 6))
    plt.plot(data['Close'], label='Price', color='black')
    plt.plot(data['MA5'], label='5MA', color='red', alpha=0.6)
    plt.plot(data['MA20'], label='20MA', color='orange', alpha=0.6)
    plt.plot(data['MA60'], label='60MA', color='blue', alpha=0.6)
    plt.title(f"{ticker} Momentum Analysis")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()


# --- 메인 실행부 ---
if __name__ == "__main__":
    # 관심 종목 리스트 (코스피는 .KS, 코스닥은 .KQ를 붙입니다)
    # 현재 시장 주도주 및 관심 섹터 종목 예시
    watchlist = [
        '036930.KS',  # 주성엔지니어링
        '005930.KS',  # 삼성전자
        '000660.KS',  # SK하이닉스
        '005380.KS',  # 현대차
        '000270.KS',  # 기아
        '066570.KS',  # LG전자
        '033100.KS',  # 재룡전기
        'NVDA',  # 엔비디아 (미국주식도 가능)
        'AAPL'  # 애플
    ]

    print("알고리즘 분석을 시작합니다...")
    recommended = analyze_momentum(watchlist)

    if recommended:
        print(f"\n총 {len(recommended)}개의 모멘텀 종목이 발견되었습니다.")
        # 첫 번째 추천 종목 차트 보기 (예시)
        plot_momentum(recommended[0]['ticker'], recommended[0]['data'])
    else:
        print("\n현재 조건에 맞는 모멘텀 종목이 없습니다.")