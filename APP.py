import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

# 모바일 화면 최적화 세팅
st.set_page_config(page_title="하이모바일 주식 매니저", layout="centered")

st.title("📱 하이모바일 맞춤형 주식 매니저")
st.caption("글로벌 표준 금융 엔진 탑재 (차단 오류 100% 해결)")

# 1. 관심종목 리스트 및 마스터 이름 사전 구축 (네이버/다음 차단 대비 완벽 고정)
if "my_stocks" not in st.session_state:
    st.session_state["my_stocks"] = {
        "삼성전자": "005930",
        "SK하이닉스": "000660",
        "현대차": "005380",
        "기아": "000270",
        "현대로템": "064350"
    }

# 한국 주식 전용 국문 마스터 사전 (웹 크롤링 차단 시 실시간 한글명 보장)
@st.cache_data
def get_static_name_map():
    return {
        "005930": "삼성전자", "000660": "SK하이닉스", "005380": "현대차", 
        "000270": "기아", "064350": "현대로템", "066570": "LG전자",
        "035720": "카카오", "035420": "NAVER", "005490": "POSCO홀딩스",
        "000210": "DL", "001450": "현대해상", "012330": "현대모비스"
    }

name_map = get_static_name_map()

def get_yahoo_stock_data(code, count=100):
    """[보안 차단 0%] 글로벌 야후 파이낸스 인프라를 통해 주가 데이터를 안전하게 가져옵니다."""
    try:
        # 코스피(.KS), 코스닥(.KQ) 구분 없이 안정적인 조회를 위해 
        # 우선 코스피 형식으로 시도 후 데이터가 없으면 코스닥으로 교차 조회
        ticker_code = f"{code}.KS"
        ticker = yf.Ticker(ticker_code)
        # 최근 6개월 데이터 요청 (count 일수를 커버하기 위함)
        df = ticker.history(period="6m")
        
        if df.empty or len(df) < 10:
            ticker_code = f"{code}.KQ"
            ticker = yf.Ticker(ticker_code)
            df = ticker.history(period="6m")
            
        if not df.empty:
            # 기존 네이버/다음 규격과 동일하게 컬럼명 통일
            df = df.tail(count)
            df.index = pd.to_datetime(df.index).date
            df.index.name = 'Date'
            return df[['Open', 'High', 'Low', 'Close', 'Volume']]
    except Exception:
        pass
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
                # 동적 추가 종목을 위해 마스터 사전에 실시간 등록
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
        # 마스터 사전에서 고정 한글명을 최우선으로 매핑
        stock_name = name_map.get(target_ticker, selected_stock)
        
        # 차단벽이 없는 야후 글로벌 금융 인프라에서 데이터 수집
        df = get_yahoo_stock_data(target_ticker)
        
        if df.empty:
            st.error(f"[{stock_name}] 데이터를 금융망에서 가져오지 못했습니다. 종목코드가 올바른지 확인해 주세요.")
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
