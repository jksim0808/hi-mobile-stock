import streamlit as st
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator

# 웹 페이지 설정
st.set_page_config(page_title="하이모바일 주식 분석기", layout="wide")

st.title("📈 실시간 상승 모멘텀 분석기")
st.sidebar.header("설정")

# 사용자가 직접 종목 입력 가능
target_stocks = st.sidebar.text_input("분석할 종목 코드를 입력하세요 (쉼표 구분)", "005930.KS, 000660.KS, 005380.KS, NVDA")
tickers = [t.strip() for t in target_stocks.split(",")]

if st.sidebar.button("분석 시작"):
    cols = st.columns(len(tickers))

    for i, ticker in enumerate(tickers):
        with st.container():
            st.subheader(f"🔍 {ticker} 분석 결과")

            # 데이터 수집
            df = yf.download(ticker, period="100d", interval="1d", progress=False, auto_adjust=True)
            if df.empty:
                st.error(f"{ticker} 데이터를 불러올 수 없습니다.")
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # 지표 계산
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA60'] = df['Close'].rolling(window=60).mean()
            df['RSI'] = RSIIndicator(close=df['Close'], window=14).rsi()

            curr_price = df['Close'].iloc[-1]
            curr_rsi = df['RSI'].iloc[-1]

            # 대시보드 메트릭 표시
            m1, m2 = st.columns(2)
            m1.metric("현재가", f"{curr_price:,.0f}")
            m2.metric("RSI 지수", f"{curr_rsi:.2f}")

            # 차트 그리기
            st.line_chart(df[['Close', 'MA20', 'MA60']])

            # 판단 로직
            if df['Close'].iloc[-1] > df['MA20'].iloc[-1] and 50 < curr_rsi < 70:
                st.success("✅ 상승 모멘텀 포착: 매수 고려 가능")
            else:
                st.info("시장의 추세를 기다리는 중입니다.")
            st.divider()