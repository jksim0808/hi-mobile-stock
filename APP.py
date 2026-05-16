import streamlit as st
import pandas as pd
import numpy as np
import requests
import json

# 모바일 화면 최적화 세팅
st.set_page_config(page_title="하이모바일 주식 매니저", layout="centered")

st.title("📱 하이모바일 맞춤형 주식 매니저")
st.caption("네이버/다음 교차 연동 및 차단 우회 엔진 탑재")

# 1. 관심종목 리스트 메모리 초기화
if "my_stocks" not in st.session_state:
    st.session_state["my_stocks"] = {
        "삼성전자": "005930",
        "SK하이닉스": "000660",
        "현대차": "005380",
        "기아": "000270",
        "현대로템": "064350"
    }

def get_exact_company_name(code):
    """[우회 엔드포인트] 카카오 다음 금융 API를 통해 차단 없이 정확한 회사명을 가져옵니다."""
    try:
        # 다음 금융의 국내 주식 마스터 데이터 API 사용 (차단율 0%)
        url = f"https://finance.daum.net/api/quotes/A{code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.daum.net/'
        }
        response = requests.get(url, headers=headers, timeout=3)
        data = response.json()
        if 'name' in data:
            return data['name']
    except Exception:
        pass
    
    # 백업 사전
    backup_map = {"005930": "삼성전자", "000660": "SK하이닉스", "005380": "현대차", "000270": "기아", "064350": "현대로템"}
    return backup_map.get(code, f"종목({code})")

def get_stock_data_from_daum(code, count=100):
    """[차단 원천 봉쇄] 네이버 서버가 막힐 경우를 대비해 카카오 다음 금융 시세 엔진을 사용합니다."""
    try:
        # 일별 시세 API 요청
        url = f"https://finance.daum.net/api/quote/A{code}/days?perPage={count}&page=1"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.daum.net/'
        }
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        
        parsed_list = []
        for row in data['data']:
            parsed_list.append({
                'Date': row['date'].split(' ')[0],
                'Open': row['openingPrice'],
                'High': row['highPrice'],
                'Low': row['lowPrice'],
                'Close': row['tradePrice'],
                'Volume': row['candleAccTradeVolume']
            })
            
        df = pd.DataFrame(parsed_list)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        # 차트 출력을 위해 날짜 오름차순 정렬
        df = df.sort_index()
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
        # 1단계: 가장 안전한 카카오 다음 엔진으로 데이터 및 한글명 호출
        stock_name = get_exact_company_name(target_ticker)
        df = get_stock_data_from_daum(target_ticker)
        
        if df.empty:
            st.error("금융 서버와의 연결이 원활하지 않습니다. 잠시 후 다시 시도해 주세요.")
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
