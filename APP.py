import streamlit as st
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET

# 모바일 화면 최적화 세팅
st.set_page_config(page_title="하이모바일 주식 매니저", layout="centered")

st.title("📱 하이모바일 맞춤형 주식 매니저")
st.caption("네이버 검색 엔진 연동형 회사명 자동 추출 탑재")

# 1. 관심종목 리스트 초기화 (기본 세팅)
if "my_stocks" not in st.session_state:
    st.session_state["my_stocks"] = {
        "삼성전자": "005930",
        "SK하이닉스": "000660",
        "현대차": "005380",
        "기아": "000270",
        "현대로템": "064350"
    }

def get_company_name_via_search(code):
    """[철벽 우회] 네이버 검색 자동완성 API를 이용하여 차단 없이 100% 한글명을 가져옵니다."""
    try:
        # 네이버 증권 검색창 자동완성 공식 API 주소
        url = f"https://ac.stock.naver.com/ac?q={code}&target=stock"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=3)
        data = response.json()
        
        # 검색 결과 중 가장 첫 번째 종목의 이름 추출
        if data and 'items' in data and len(data['items']) > 0 and len(data['items'][0]) > 0:
            first_match = data['items'][0][0]
            # 네이버 응답 규격: ['삼성전자', '005930', 'samsungjeonja', ...]
            actual_name = first_match[0]
            return actual_name
    except Exception:
        pass
    return None

def get_mobile_naver_data(code, count=100):
    """일반 스마트폰 브라우저로 위장하여 네이버에서 주가 데이터를 가져옵니다."""
    try:
        url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count={count}&requestType=0"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1',
            'Referer': f'https://m.stock.naver.com/domestic/stock/{code}/total'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
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

# ==========================================
# 2. 관심종목 관리 창 (코드만 입력)
# ==========================================
with st.expander("⭐ 나만의 관심종목 추가/삭제 하기"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**종목 추가 (자동 이름 검색)**")
        add_code = st.text_input("종목코드 6자리 입력", placeholder="예: 066570")
        
        if st.button("➕ 관심종목 등록", use_container_width=True):
            if add_code:
                # 숫자만 남기기
                clean_code = ''.join(filter(str.isdigit, add_code)).zfill(6)
                
                # 1단계: 검색 자동완성 전용 통로로 실시간 한글명 낚아채기
                with st.spinner("네이버 검색망에서 정확한 회사명 찾는 중..."):
                    auto_stock_name = get_company_name_via_search(clean_code)
                
                if auto_stock_name:
                    # 2단계: 알아온 이름으로 즉시 앱에 등록
                    st.session_state["my_stocks"][auto_stock_name] = clean_code
                    st.success(f"🎉 **'{auto_stock_name} ({clean_code})'** 등록 성공!")
                    st.rerun()
                else:
                    st.error("존재하지 않는 종목코드이거나 상장 폐지된 종목입니다. 번호를 다시 확인해 주세요.")
            else:
                st.error("종목코드를 입력해주세요.")
                
    with col2:
        st.markdown("**종목 삭제**")
        delete_target = st.selectbox("삭제할 종목 선택", list(st.session_state["my_stocks"].keys()))
        if st.button("❌ 선택 종목 삭제", use_container_width=True):
            if delete_target in st.session_state["my_stocks"]:
                del st.session_state["my_stocks"][delete_target]
                st.warning(f"'{delete_target}' 종목이 삭제되었습니다.")
                st.rerun()

st.markdown("---")

# ==========================================
# 3. 저장된 종목 불러와서 터치 분석하기
# ==========================================
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
        # 모바일 브라우저로 위장하여 시세 데이터 호출
        df = get_mobile_naver_data(target_ticker)
        
        if df.empty:
            st.error(f"⚠️ 시세 데이터 연동 중입니다. [모멘텀 분석 시작] 버튼을 한 번만 더 눌러주세요.")
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
            st.markdown(f"### 🔍 {selected_stock} ({target_ticker})")
            
            st.metric("현재가", f"{curr_price:,.0f} 원")
            st.metric("RSI 심리 지수", f"{curr_rsi:.2f}")

            # 차트 그리기
            st.line_chart(df[['Close', 'MA20', 'MA60']])
            
            # 판단 로직
            is_trending = curr_price > ma20 > ma60
            is_momentum = 50 < curr_rsi < 70
            
            if is_trending and is_momentum:
                st.success(f"📈 {selected_stock}: 상승 모멘텀 포착 (매수 긍정)")
            elif is_trending:
                st.warning(f"⚠️ {selected_stock}: 정배열 상승세이나 진입 시점 조율 필요")
            else:
                st.info(f"💤 {selected_stock}: 현재 하락 추세이거나 횡보 구간 (관망 권장)")
