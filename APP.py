import streamlit as st
import pandas as pd
import numpy as np
import requests

# 웹 페이지 설정
st.set_page_config(page_title="하이모바일 네이버 주식 분석기", layout="wide")

st.title("📈 네이버 금융 연동 상승 모멘텀 분석기")
st.sidebar.header("설정")

# 사용자가 직접 한국 주식 종목코드 입력 (6자리 숫자)
target_stocks = st.sidebar.text_input("분석할 종목 코드를 입력하세요 (쉼표 구분)", "005930, 000660, 005380, 000270")
tickers = [t.strip() for t in target_stocks.split(",")]


def get_naver_stock_data(code, count=100):
    """네이버 금융에서 일별 시세를 가져오는 함수"""
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count={count}&requestType=0"
    try:
        # 네이버 차트 데이터 데이터 요청
        response = requests.get(url)
        # XML 데이터 파싱
        df = pd.read_xml(response.text, xpath="//item")
        df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']

        # 날짜 형식 및 숫자 형식 변환
        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = df[col].astype(float)

        df.set_index('Date', inplace=True)
        return df
    except Exception as e:
        return pd.DataFrame()


def calculate_rsi(series, period=14):
    """파이썬 기본 연산으로 RSI 계산 (외부 라이브러리 의존 제거)"""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)

    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()

    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))


if st.sidebar.button("네이버 데이터 분석 시작"):
    for ticker in tickers:
        with st.container():
            st.subheader(f"🔍 종목코드: {ticker} 분석 결과")

            # 1. 데이터 수집
            df = get_naver_stock_data(ticker)
            if df.empty:
                st.error(f"[{ticker}] 코드를 확인해 주세요. (6자리 숫자 입력)")
                continue

            # 2. 기술적 지표 계산
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA60'] = df['Close'].rolling(window=60).mean()
            df['RSI'] = calculate_rsi(df['Close'])

            curr_price = df['Close'].iloc[-1]
            curr_rsi = df['RSI'].iloc[-1]
            ma20 = df['MA20'].iloc[-1]
            ma60 = df['MA60'].iloc[-1]

            # 3. 대시보드 화면 표시
            m1, m2 = st.columns(2)
            m1.metric("현재가 (원)", f"{curr_price:,.0f}")
            m2.metric("RSI 지수", f"{curr_rsi:.2f}")

            # 차트 시각화 (종가 및 이동평균선)
            st.line_chart(df[['Close', 'MA20', 'MA60']])

            # 4. 국내 시장 맞춤형 모멘텀 판단 로직
            is_trending = curr_price > ma20 > ma60
            is_momentum = 50 < curr_rsi < 70

            if is_trending and is_momentum:
                st.success("✅ 네이버 데이터 기준: 상승 모멘텀 포착 (매수 긍정)")
            elif is_trending:
                st.warning("⚠️ 안정적인 정배열 상승 추세이나, 진입 시점 조율 필요")
            else:
                st.info("현재 하락 추세이거나 횡보 구간입니다. 관망을 권장합니다.")
            st.divider()