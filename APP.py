import streamlit as st
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET

# 웹 페이지 설정
st.set_page_config(page_title="하이모바일 주식 분석기", layout="wide")

st.title("📈 네이버 금융 연동 상승 모멘텀 분석기")
st.sidebar.header("설정")

# 사용자가 직접 한국 주식 종목코드 입력
target_stocks = st.sidebar.text_input("분석할 종목 코드를 입력하세요 (쉼표 구분)", "005930, 000660, 005380, 000270, 064350")
tickers = [t.strip() for t in target_stocks.split(",")]

def get_fallback_company_name(code):
    """[최종 마스터 안전장치] 주말/야간에도 차단되지 않는 네이버 차트 설정 정보에서 순수 회사명을 추출합니다."""
    try:
        # 이 주소는 주말에도 항상 열려 있으며, 해당 종목의 한글 이름을 포함하고 있습니다.
        url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=1&requestType=0"
        response = requests.get(url)
        root = ET.fromstring(response.text)
        
        # XML 구조의 <chartinfo item="삼성전자" ...> 에서 item 속성(회사명)을 가져옵니다.
        chart_info = root.find('.//chartinfo')
        if chart_info is not None:
            name = chart_info.get('item')
            if name:
                return name
    except Exception:
        pass
    return f"종목({code})"

def get_exact_company_name(code):
    """실시간 API 조회를 시도하고, 주말/야간이라 실패하면 2차 마스터 장치를 가동합니다."""
    try:
        url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers)
        data = response.json()
        stock_name = data['result']['areas'][0]['datas'][0]['nm']
        if stock_name:
            return stock_name
    except Exception:
        pass
    
    # 주말/야간 조회를 위한 구원 투수 등판
    return get_fallback_company_name(code)

def get_naver_stock_data(code, count=100):
    """네이버 금융에서 일별 시세를 가져오는 함수"""
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count={count}&requestType=0"
    try:
        response = requests.get(url)
        root = ET.fromstring(response.text)
        
        parsed_data = []
        for item in root.findall('.//item'):
            data_row = item.get('data').split('|')
            parsed_data.append(data_row)
            
        if not parsed_data:
            return pd.DataFrame()
            
        df = pd.DataFrame(parsed_data, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df.set_index('Date', inplace=True)
        return df
    except Exception:
        return pd.DataFrame()

def calculate_rsi(series, period=14):
    """RSI 계산 수식"""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

# 분석 실행
if st.sidebar.button("네이버 데이터 분석 시작"):
    for ticker in tickers:
        clean_ticker = ''.join(filter(str.isdigit, ticker))
        if len(clean_ticker) < 6:
            clean_ticker = clean_ticker.zfill(6)
        
        # 주말/장마감 상관없이 상장된 모든 종목의 이름을 가져오는 함수 호출
        stock_name = get_exact_company_name(clean_ticker)
        
        with st.container():
            st.subheader(f"🔍 {stock_name} ({clean_ticker}) 분석 결과")
            
            # 데이터 수집
            df = get_naver_stock_data(clean_ticker)
            if df.empty:
                st.error(f"[{stock_name}] 데이터를 불러오지 못했습니다. 코드를 확인해 주세요.")
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
                st.success(f"✅ {stock_name}: 상승 모멘텀 포착 (매수 긍정)")
            elif is_trending:
                st.warning(f"⚠️ {stock_name}: 안정적인 정배열 상승 추세이나, 진입 시점 조율 필요")
            else:
                st.info(f"{stock_name}: 현재 하락 추세이거나 횡보 구간입니다. 관망을 권장합니다.")
            st.divider()
