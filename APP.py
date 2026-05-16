import streamlit as st
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET

# 웹 페이지 설정
st.set_page_config(page_title="하이모바일 네이버 주식 분석기", layout="wide")

st.title("📈 네이버 금융 연동 상승 모멘텀 분석기")
st.sidebar.header("설정")

# 사용자가 직접 한국 주식 종목코드 입력
target_stocks = st.sidebar.text_input("분석할 종목 코드를 입력하세요 (쉼표 구분)", "005930, 000660, 005380, 000270")
tickers = [t.strip() for t in target_stocks.split(",")]

def get_naver_stock_data(code, count=100):
    """네이버 금융에서 일별 시세를 안전하게 가져오는 보완된 함수"""
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count={count}&requestType=0"
    try:
        response = requests.get(url)
        # 1. XML 데이터를 전통적인 방식으로 안전하게 파싱
        root = ET.fromstring(response.text)
        
        parsed_data = []
        for item in root.findall('.//item'):
            # 데이터가 공백으로 구분되어 있으므로 잘라서 리스트화
            data_row = item.get('data').split('|')
            parsed_data.append(data_row)
            
        if not parsed_data:
            return pd.DataFrame()
            
        # 2. 데이터프레임 생성 및 컬럼 지정
        df = pd.DataFrame(parsed_data, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        
        # 3. 타입 변환 (날짜 및 숫자)
        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df.set_index('Date', inplace=True)
        return df
    except Exception as e:
        return pd.DataFrame()

def calculate_rsi(series, period=14):
    """파이썬 기본 연산으로 RSI 계산"""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

if st.sidebar.button("네이버 데이터 분석 시작"):
    for ticker in tickers:
        # 혹시나 사용자가 .KS를 붙여서 입력했을 경우를 대비해 숫자만 추출하는 안전장치 추가
        clean_ticker = ''.join(filter(str.isdigit, ticker))
        
        with st.container():
            st.subheader(f"🔍 종목코드: {clean_ticker} 분석 결과")
            
            # 데이터 수집
            df = get_naver_stock_data(clean_ticker)
            if df.empty:
                st.error(f"[{clean_ticker}] 데이터를 네이버에서 불러오지 못했습니다. 종목코드를 다시 확인해 주세요.")
                continue

            # 기술적 지표 계산
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA60'] = df['Close'].rolling(window=60).mean()
            df['RSI'] = calculate_rsi(df['Close'])

            curr_price = df['Close'].iloc[-1]
            curr_rsi = df['RSI'].iloc[-1]
            ma20 = df['MA20'].iloc[-1]
            ma60 = df['MA60'].iloc[-1]

            # 대시보드 화면 표시
            m1, m2 = st.columns(2)
            m1.metric("현재가 (원)", f"{curr_price:,.0f}")
            m2.metric("RSI 지수", f"{curr_rsi:.2f}")

            # 차트 시각화
            st.line_chart(df[['Close', 'MA20', 'MA60']])
            
            # 모멘텀 판단 로직
            is_trending = curr_price > ma20 > ma60
            is_momentum = 50 < curr_rsi < 70
            
            if is_trending and is_momentum:
                st.success("✅ 네이버 데이터 기준: 상승 모멘텀 포착 (매수 긍정)")
            elif is_trending:
                st.warning("⚠️ 안정적인 정배열 상승 추세이나, 진입 시점 조율 필요")
            else:
                st.info("현재 하락 추세이거나 횡보 구간입니다. 관망을 권장합니다.")
            st.divider()
