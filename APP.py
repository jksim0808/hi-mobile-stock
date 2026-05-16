import streamlit as st
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET

# 모바일 화면 최적화 세팅
st.set_page_config(page_title="하이모바일 주식 매니저", layout="centered")

st.title("📱 하이모바일 맞춤형 주식 매니저")
st.caption("다중 종목 일괄 등록 엔진 탑재 (쉼표/줄바꿈 지원)")

# 1. 관심종목 리스트 초기화 (기본 세팅)
if "my_stocks" not in st.session_state:
    st.session_state["my_stocks"] = {
        "삼성전자": "005930",
        "SK하이닉스": "000660",
        "현대차": "005380",
        "기아": "000270",
        "현대로템": "064350"
    }

def get_mobile_naver_data(code, count=100):
    """일반 스마트폰 브라우저로 위장하여 네이버에서 주가 데이터를 안전하게 가져옵니다."""
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
# 2. 관심종목 관리 창 (여러 개 동시에 입력 가능)
# ==========================================
with st.expander("⭐ 나만의 관심종목 대량 등록/삭제 하기"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**종목 일괄 추가**")
        st.caption("형식: '이름:코드' 형태로 적어주세요. 쉼표(,)나 줄바꿈으로 여러 개 입력이 가능합니다.")
        
        # 큰 텍스트 입력창 제공 (스마트폰에서 복사/붙여넣기 편리하도록)
        bulk_input = st.text_area(
            "종목 리스트 입력", 
            placeholder="예시:\nLG전자:066570, 카카오:035720\n네이버:035420\n삼성SDI:006400",
            height=120
        )
        
        if st.button("➕ 입력한 종목 모두 등록", use_container_width=True):
            if bulk_input:
                # 쉼표(,)와 줄바꿈(\n)을 기준으로 입력값 쪼개기
                raw_items = re.split(r'[,\n]', bulk_input) if 're' in globals() else bulk_input.replace('\n', ',').split(',')
                import re
                raw_items = re.split(r'[,\n]', bulk_input)
                
                success_count = 0
                for item in raw_items:
                    if ":" in item:
                        name_part, code_part = item.split(":", 1)
                        clean_name = name_part.strip()
                        clean_code = ''.join(filter(str.isdigit, code_part)).zfill(6)
                        
                        if clean_name and len(clean_code) == 6:
                            st.session_state["my_stocks"][clean_name] = clean_code
                            success_count += 1
                
                if success_count > 0:
                    st.success(f"🎉 총 {success_count}개의 종목이 성공적으로 추가되었습니다!")
                    st.rerun()
                else:
                    st.error("입력 형식이 올바르지 않습니다. '종목명:종목코드' 형태로 입력했는지 확인해 주세요.")
            else:
                st.error("종목 데이터를 입력해 주세요.")
                
    with col2:
        st.markdown("**종목 비우기**")
        delete_target = st.selectbox("삭제할 종목 선택", list(st.session_state["my_stocks"].keys()))
        if st.button("❌ 선택 종목 삭제", use_container_width=True):
            if delete_target in st.session_state["my_stocks"]:
                del st.session_state["my_stocks"][delete_target]
                st.warning(f"'{delete_target}' 종목이 삭제되었습니다.")
                st.rerun()
                
        if st.button("🔥 관심종목 전체 초기화", use_container_width=True):
            st.session_state["my_stocks"] = {}
            st.error("모든 관심종목이 비워졌습니다.")
            st.rerun()

st.markdown("---")

# ==========================================
# 3. 저장된 종목 불러와서 터치 분석하기
# ==========================================
st.subheader("저장된 관심종목 목록")
options_list = list(st.session_state["my_stocks"].keys())

if not options_list:
    st.info("등록된 관심종목이 없습니다. 위의 관리 창에서 대량 등록을 진행해 주세요.")
else:
    # 모바일에서 한눈에 들어오도록 라디오 버튼 배치
    selected_stock = st.radio("분석할 종목을 터치하세요:", options_list, horizontal=True)
    target_ticker = st.session_state["my_stocks"][selected_stock]
    st.info(f"선택된 종목: **{selected_stock} ({target_ticker})**")
    
    # 분석 시작 버튼
    if st.button("🚀 모멘텀 분석 시작", use_container_width=True):
        df = get_mobile_naver_data(target_ticker)
        
        if df.empty:
            st.error(f"⚠️ 금융 시세 서버에서 데이터를 가져오는 중입니다. [모멘텀 분석 시작] 버튼을 한 번 더 눌러주세요.")
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
