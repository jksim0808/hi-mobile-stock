import streamlit as st
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET
import time
import re

# 모바일 화면 최적화 및 와이드 레이아웃 설정
st.set_page_config(page_title="하이모바일 주식 매니저", layout="wide")

st.title("📊 하이모바일 커스텀 주식 스크리닝 매니저")
st.caption("RSI 지표 보정 및 대세 추세 필터링 통합 시스템")

# 기본 가이드라인용 50대 종목 초기 텍스트 세팅
DEFAULT_STOCKS_TEXT = (
    "삼성전자:005930, SK하이닉스:000660, 한미반도체:042700, 리노공업:058470, "
    "이오테크닉스:039030, HPSP:403870, 가온칩스:454840, 오픈에지테크놀로지:394280, "
    "에이직랜드:445090, 주성엔지니어링:036930, 현대차:005380, 기아:000270, "
    "현대로템:064350, 현대모비스:012330, HL만도:204320, HD현대인프라코어:042670, "
    "한국항공우주:047810, 한화에어로스페이스:012450, LIGnex1:079550, 두산로보틱스:454910, "
    "레인보우로보틱스:277810, 뉴로메카:348340, LG에너지솔루션:373220, 삼성SDI:006400, "
    "포스코퓨처엠:003670, 에코프로비엠:247540, 엘앤에프:066970, HD현대일렉트릭:043200, "
    "효성중공업:298040, LS일렉트릭:010120, 두산에너빌리티:034020, 한화솔루션:009830, "
    "씨에스윈드:112610, 삼성바이오로직스:207940, 셀트리온:068270, 유한양행:000100, "
    "알테오젠:196170, 리그켐바이오:141080, 에이비엘바이오:298380, 휴젤:145020, "
    "메디톡스:086900, 한미약품:128940, SK바이오팜:326030, KB금융:105560, "
    "신한지주:055550, 하나금융지주:086790, 메리츠금융지주:138040, 삼성물산:028260, "
    "SK:034730, POSCO홀딩스:005490"
)

def get_mobile_naver_data(code, count=80):
    """네이버 금융 피드에서 주가 데이터 추출"""
    try:
        url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count={count}&requestType=0"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1',
            'Referer': f'https://m.stock.naver.com/domestic/stock/{code}/total'
        }
        response = requests.get(url, headers=headers, timeout=3)
        root = ET.fromstring(response.text)
        parsed_data = []
        for item in root.findall('.//item'):
            data_row = item.get('data').split('|')
            parsed_data.append(data_row)
        if not parsed_data: return pd.DataFrame()
        df = pd.DataFrame(parsed_data, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame()

def calculate_rsi(series, period=14):
    """RSI 지표 계산"""
    delta = series.diff()
    up, down = delta.clip(lower=0), -delta.clip(upper=0)
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    return 100 - (100 / (1 + (ema_up / ema_down)))

# ==========================================
# 보정된 3단계 판단 로직 가이드라인 탑재
# ==========================================
with st.expander("📖 보정형(Trend-Adaptive) 3단계 판단 로직 매매 전략", expanded=False):
    st.markdown("""
    기존 RSI의 단점(강세장에서 지표가 내려오지 않는 현상)을 극복하기 위해 **장기 추세 추종형 보정 필터**를 적용했습니다.
    
    ### 1️⃣ 📈 매수 긍정 (강세장 안정적 눌림목 구간)
    *   **정량적 기준**: `현재가 > 20일선 > 60일선(정배열)` **AND** `45 ≤ RSI ≤ 65`
    *   **보정 원리**: 우량주가 대세 상승 국면에 있을 때는 RSI가 30(과매도)까지 잘 떨어지지 않습니다. 따라서 강세장 유지를 전제로 단기 과열(RSI 70 이상)을 식히고 턴어라운드하는 **RSI 45~65의 허리~어깨 진입 타이밍**을 가장 안전한 매수 적기로 포착합니다.
    
    ### 2️⃣ ⚠️ 진입 조율 필요 (단기 급등 과열 또는 추세 둔화)
    *   **정량적 기준**: `현재가 > 20일선 > 60일선(정배열)` **AND** `(RSI > 65 또는 RSI < 45)`
    *   **보정 원리**:
        *   **RSI 65 초과 (단기 과열 고점권)**: 추세는 좋으나 과매수 구역에 임박하여 언제든 차익실현 매물이 쏟아질 수 있는 자리입니다. (추격 매수 자제, 보유자 영역)
        *   **RSI 45 미만 (추세 붕괴 위험 조짐)**: 정배열은 유지 중이나 단기 낙폭이 깊어 20일선 이탈 후 매물이 쌓이는 리스크 구간입니다. 지지선 확인이 선행되어야 합니다.
    
    ### 3️⃣ 💤 관망 권장 (하락 역배열 또는 박스권 소외)
    *   **정량적 기준**: 위의 정배열 조건을 만족하지 못하는 모든 역배열/데드크로스 종목 (`현재가 < 20일선` 혹은 `20일선 < 60일선`)
    *   **보정 원리**: 머리 위의 매물 저항이 심하고 기관·외인의 수급 둔화가 지속되는 역배열 구간입니다. RSI가 아무리 낮아도(과매도 상태) 주가가 추가 하락할 위험이 크므로 확실한 추세 전환 전까지 관망을 유지합니다.
    """)

# ==========================================
# 상단 컨트롤 타워: 내 마음대로 종목 편집창
# ==========================================
with st.expander("🛠️ 분석 대상 종목 리스트 자유롭게 변경하기 (추가/삭제/수정)", expanded=False):
    st.markdown("**형식 가이드**: `종목명:6자리코드` 형태로 작성하고, 각 종목은 **쉼표(,)나 줄바꿈(엔터)**으로 구분해 주세요.")
    
    user_stocks_input = st.text_area(
        "현재 분석 대상 리스트 (원하는 대로 지우거나 추가해 보세요)",
        value=DEFAULT_STOCKS_TEXT,
        height=120
    )

# 텍스트 파싱하여 딕셔너리로 동적 변환
current_stocks_map = {}
raw_items = re.split(r'[,\n]', user_stocks_input)
for item in raw_items:
    if ":" in item:
        name_part, code_part = item.split(":", 1)
        clean_name = name_part.strip()
        clean_code = ''.join(filter(str.isdigit, code_part)).zfill(6)
        if clean_name and len(clean_code) == 6:
            current_stocks_map[clean_name] = clean_code

st.info(f"📋 현재 설정된 분석 대상 종목: 총 **{len(current_stocks_map)}**개")

# ==========================================
# 메인 제어 분석 실행
# ==========================================
if st.button("🚀 보정형 스크리닝 엔진 전수 분석 시작", use_container_width=True):
    if not current_stocks_map:
        st.error("분석할 종목이 없습니다. 위의 편집창에 '종목명:종목코드' 형태로 입력되어 있는지 확인해 주세요.")
    else:
        group_success = []  # 📈 매수 긍정 (정배열 골디락스)
        group_warning = []  # ⚠️ 진입 조율 필요 (과열 또는 지지선 이탈 조짐)
        group_info = []     # 💤 관망 권장 (역배열 및 횡보)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_stocks = len(current_stocks_map)
        
        for idx, (name, code) in enumerate(current_stocks_map.items()):
            status_text.text(f"⏳ 데이터 연산 및 보정 필터링 중 ({idx+1}/{total_stocks}): {name} ({code})")
            progress_bar.progress((idx + 1) / total_stocks)
            
            df = get_mobile_naver_data(code)
            if df.empty:
                time.sleep(0.1)
                df = get_mobile_naver_data(code)
                
            if not df.empty:
                # 이동평균선 및 지표 연산
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA60'] = df['Close'].rolling(window=60).mean()
                df['RSI'] = calculate_rsi(df['Close'])
                
                curr_price = int(df['Close'].iloc[-1])
                curr_rsi = float(df['RSI'].iloc[-1])
                ma20 = float(df['MA20'].iloc[-1])
                ma60 = float(df['MA60'].iloc[-1])
                
                stock_info = {
                    "종목명": name,
                    "종목코드": code,
                    "현재가": f"{curr_price:,.0f}원",
                    "RSI": f"{curr_rsi:.1f}"
                }
                
                # [보정 핵심] 장기 추세 정배열 유무 판정
                is_trending = curr_price > ma20 > ma60
                
                # 강세장 속 안전한 무릎~어깨 수급 강도 대입 (45선 지지 및 65 이하 안정권)
                is_bullish_pullback = 45 <= curr_rsi <= 65
                
                if is_trending and is_bullish_pullback:
                    group_success.append(stock_info)
                elif is_trending:
                    # 정배열이지만 과매수(RSI > 65)이거나 단기 과매도(RSI < 45)로 일탈한 경우
                    group_warning.append(stock_info)
                else:
                    # 이평선 역배열, 주가가 이평선 아래에 침전해 있는 역추세 경우
                    group_info.append(stock_info)
                    
            time.sleep(0.04) # 금융 서버 트래픽 마진
            
        status_text.text(f"✅ 총 {total_stocks}개 종목의 추세 보정 스크리닝이 완료되었습니다!")
        progress_bar.empty()
        
        # ==========================================
        # 3분할 대시보드 결과 출력
        # ==========================================
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.success(f"📈 매수 긍정 ({len(group_success)}개)")
            st.caption("강세 정배열 + RSI 45~65 사이의 골디락스/눌림목")
            if group_success:
                st.dataframe(pd.DataFrame(group_success), use_container_width=True, hide_index=True)
            else:
                st.info("조건에 일치하는 종목이 없습니다.")
                
        with col2:
            st.warning(f"⚠️ 진입 조율 필요 ({len(group_warning)}개)")
            st.caption("정배열이나 단기 과열(RSI>65) 혹은 단기 낙폭 과대(RSI<45)")
            if group_warning:
                st.dataframe(pd.DataFrame(group_warning), use_container_width=True, hide_index=True)
            else:
                st.info("조건에 일치하는 종목이 없습니다.")
                
        with col3:
            st.info(f"💤 관망 권장 ({len(group_info)}개)")
            st.caption("현재 하락 역배열 구간이거나 박스권 소외 종목")
            if group_info:
                st.dataframe(pd.DataFrame(group_info), use_container_width=True, hide_index=True)
            else:
                st.info("조건에 일치하는 종목이 없습니다.")
