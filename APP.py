import streamlit as st
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET

# 1. 모바일 화면에 꽉 차게 설정
st.set_page_config(page_title="하이모바일 주식 매니저", layout="centered")

st.title("📱 하이모바일 모바일 주식 매니저")
st.caption("스마트폰 및 태블릿 전용 화면")

# 2. 터치하기 쉬운 주요 대형주 '원터치 버튼' 세팅
st.subheader("심플 종목 선택")
selected_preset = st.radio(
    "자주 보는 종목을 터치하세요:",
    ["직접 입력", "삼성전자", "SK하이닉스", "현대차", "기아", "현대로템", "LG전자"],
    horizontal=True # 버튼들을 가로로 배치하여 손가락으로 누르기 편하게 만듭니다.
)

# 라디오 버튼 선택에 따른 코드 매핑
preset_map = {
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "현대차": "005380",
    "기아": "000270",
    "현대로템": "064350",
    "LG전자": "066570"
}

# 3. 입력창 자동화 처리
if selected_preset == "직접 입력":
    target_input = st.text_input("종목 코드를 입력하세요 (예: 005930)", "005930")
else:
    # 버튼을 누르면 입력창에 코드가 자동으로 들어갑니다.
    target_input = preset_map[selected_preset]
    st.info(f"선택된 종목 코드: **{target_input}**")

def get_data_and_name(code, count=100):
    """네이버 서버에서 주가 데이터와 한글 회사명을 동시에 추출하는 마스터 함수"""
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count={count}&requestType=0"
    try:
        response = requests.get(url)
        root = ET.fromstring(response.text)
        
        chart_info = root.find('.//chartinfo')
        stock_name = chart_info.get('item') if chart_info is not None else f"종목({code})"
        
        parsed_data = []
        for item in root.findall('.//item'):
            data_row = item.get('data').split('|')
            parsed_data.append(data_row)
            
        if not parsed_data:
            return pd.DataFrame(), stock_name
            
        df = pd.DataFrame(parsed_data, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df.set_index('Date', inplace=True)
        return df, stock_name
    except Exception:
        return pd.DataFrame(), f"종목({code})"

def calculate_rsi(series, period=14):
    """RSI 기술적 지표 계산 수식"""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

st.markdown("---")

# 4. 스마트폰 전용 큰 규격의 분석 버튼
if st.button("🚀 모멘텀 분석 시작", use_container_width=True):
    clean_ticker = ''.join(filter(str.isdigit, target_input)).zfill(6)
    df, stock_name = get_data_and_name(clean_ticker)
    
    if df.empty:
        st.error("데이터를 불러오지 못했습니다. 코드를 확인해 주세요.")
    else:
        # 기술적 지표 계산
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['RSI'] = calculate_rsi(df['Close'])

        curr_price = df['Close'].iloc[-1]
        curr_rsi = df['RSI'].iloc[-1]
        ma20 = df['MA20'].iloc[-1]
        ma60 = df['MA60'].iloc[-1]

        # 결과 타이틀
        st.markdown(f"### 🔍 {stock_name} ({clean_ticker})")
        
        # 5. 모바일 세로 화면을 고려해 수치 지표를 위아래로 깔끔하게 배치
        st.metric("현재가", f"{curr_price:,.0f} 원")
        st.metric("RSI 심리 지수", f"{curr_rsi:.2f}")

        # 차트 화면 (모바일 뷰 최적화)
        st.line_chart(df[['Close', 'MA20', 'MA60']])
        
        # 모멘텀 판단 로직 및 큼직한 결과창
        is_trending = curr_price > ma20 > ma60
        is_momentum = 50 < curr_rsi < 70
        
        if is_trending and is_momentum:
            st.success(f"📈 {stock_name}: 상승 모멘텀 포착 (매수 긍정)")
        elif is_trending:
            st.warning(f"⚠️ {stock_name}: 정배열 상승세이나 진입 시점 조율 필요")
        else:
            st.info(f"💤 {stock_name}: 현재 하락 추세이거나 횡보 구간 (관망 권장)")
