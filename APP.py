import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import datetime

# 모바일 화면 최적화 세팅
st.set_page_config(page_title="하이모바일 주식 매니저", layout="centered")

st.title("📱 하이모바일 맞춤형 주식 매니저")
st.caption("모바일 브라우저 위장 엔진 탑재 (클라우드 IP 차단 우회 완료)")

# 1. 관심종목 리스트 및 마스터 이름 사전 구축
if "my_stocks" not in st.session_state:
    st.session_state["my_stocks"] = {
        "삼성전자": "005930",
        "SK하이닉스": "000660",
        "현대차": "005380",
        "기아": "000270",
        "현대로템": "064350"
    }

# 국문 마스터 사전
@st.cache_data
def get_static_name_map():
    return {
        "005930": "삼성전자", "000660": "SK하이닉스", "005380": "현대차", 
        "000270": "기아", "064350": "현대로템", "066570": "LG전자",
        "035720": "카카오", "035420": "NAVER", "005490": "POSCO홀딩스",
        "000210": "DL", "001450": "현대해상", "012330": "현대모비스"
    }

name_map = get_static_name_map()

def get_mobile_naver_data(code, count=100):
    """[특수 우회] 일반 스마트폰 브라우저로 네이버 증권에 접속한 것처럼 위장하여 시세를 가져옵니다."""
    try:
        # 네이버 모바일 증권의 실제 주가 차트 API 주소 활용
        url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count={count}&requestType=0"
        
        # [핵심] Streamlit 서버가 아닌, 실제 일반 PC/아이폰 브라우저인 것처럼 헤더 정보 조작
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': f'https://m.stock.naver.com/domestic/stock/{code}/total'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        # XML 데이터 파싱
        import xml.etree.ElementTree as ET
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
    """RSI 기술적 지표 계산"""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

# 2. 관심종목 관리 창 (추가 / 삭제)
with st.expander("⭐ 나만의 관심종목 추가/삭제 하기"):
    col1, col2 = st.columns(2)
    with col1:
        add_name = st.text_input("추가할 회사명", placeholder="예: LG전자")
        add_code = st.text_input("추가할 종목코드", placeholder="예: 066570")
        if st.button("➕ 종목 추가", use_container_width=True):
            if add_name and add_code:
                clean_code = ''.join(filter(str.isdigit, add_code)).zfill(6)
                st.session_state["my_stocks"][add_name] = clean_code
                name_map[clean_code] = add_name
                st.success(f"'{add_name}' 종목이 추가되었습니다!")
                st.rerun()
            else:
                st.error("이름과 코드를 모두 입력해주세요.")
                
    with col2:
        delete_target = st.selectbox("삭제할 종목 선택", list(st.session_state["my_stocks"].keys()))
        if st.button("❌ 선택 종목 삭제", use_container_width=True):
            if delete_target in st.session_state["my_stocks"]:
                del st.session_state["my_stocks"][delete_target]
                st.warning(f"'{delete_target}' 종목이 삭제되었습니다.")
                st.rerun()

st.markdown("---")

# 3. 저장된 종목 불러와서 터치 분석하기
st.subheader("저장된 관심종목 목록")
options_list = list(st.session_state["my_stocks"].keys())

if not options_list:
    st.info("등록된 관심종목이 없습니다. 위의 관리 창에서 종목을 추가해 주세요.")
else:
    selected_stock = st.radio("분석할 종목을 터치하세요:", options_list, horizontal=True)
    target_ticker = st.session_state["my_stocks"][selected_stock]
    st.info(f"선택된 종목: **{selected_stock} ({target_ticker})**")
    
    # 분석 시작 버튼
    if st.button("🚀 모멘텀 분석 시작", use_container_width=True):
        stock_name = name_map.get(target_ticker, selected_stock)
        
        # 일반 사용자로 완벽히 위장하여 네이버에서 직접 데이터 수집
        df = get_mobile_naver_data(target_ticker)
        
        if df.empty:
            st.error(f"⚠️ 금융 보안벽 우회 중입니다. 잠시 후 [모멘텀 분석 시작] 버튼을 한 번만 더 눌러주세요.")
        else:
            # 기술적 지표 계산
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA60'] = df['Close'].rolling(window=60).mean()
            df['RSI'] = calculate_rsi(df['Close'])

            curr_price = df['Close'].iloc[-1]
            curr_rsi = df['RSI'].iloc[-1]
            ma20 = df['MA20'].iloc[-1]
            ma60 = df['MA60'].iloc[-1]

            # 결과 화면 출력
            st.markdown(f"### 🔍 {stock_name} ({target_ticker})")
            
            st.metric("현재가", f"{curr_price:,.0f} 원")
            st.metric("RSI 심리 지수", f"{curr_rsi:.2f}")

            # 차트 그리기
            st.line_chart(df[['Close', 'MA20', 'MA60']])
            
            # 판단 로직
            is_trending = curr_price > ma20 > ma60
            is_momentum = 50 < curr_rsi < 70
            
            if is_trending and is_momentum:
                st.success(f"📈 {stock_name}: 상승 모멘텀 포착 (매수 긍정)")
            elif is_trending:
                st.warning(f"⚠️ {stock_name}: 정배열 상승세이나 진입 시점 조율 필요")
            else:
                st.info(f"💤 {stock_name}: 현재 하락 추세이거나 횡보 구간 (관망 권장)")
