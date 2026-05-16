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
st.caption("내 마음대로 편집하는 실시간 모멘텀 필터링 시스템")

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
# [신설] 3단계 판단 로직 구체적 가이드라인 탑재
# ==========================================
with st.expander("📖 시스템 3단계 핵심 판단 로직 및 매매 전략 설명서", expanded=False):
    st.markdown("""
    본 시스템은 주가의 **중장기 추세 방향성(이동평균선)**과 **단기 수급의 심리적 과열 상태(RSI)**를 결합하여 투자 리스크를 최소화하도록 설계된 스크리닝 엔진입니다.
    
    ### 1️⃣ 📈 매수 긍정 (상승 모멘텀 포착)
    *   **정량적 기술 지표 기준**: `현재가 > 20일 이평선 > 60일 이평선` **AND** `50 < RSI < 70`
    *   **차트 해석**: 주가가 중장기 상승 가속도 구간(정배열 상승 추세)에 안착해 있으면서, 단기 과열권(RSI 70 이상)에 도달하기 직전의 가장 탄력적인 무릎~어깨 구간입니다. 
    *   **대응 전략**: 기관·외인 수급 유입이 가장 강한 타이밍이므로 **신규 진입 및 분할 매수** 관점에서 매우 유망합니다.
    
    ### 2️⃣ ⚠️ 진입 조율 필요 (추세 지속 및 과열 주의)
    *   **정량적 기술 지표 기준**: `현재가 > 20일 이평선 > 60일 이평선` **AND** `(RSI ≥ 70 또는 RSI ≤ 50)`
    *   **차트 해석**: 대세 상승 추세(정배열)는 유지되고 있으나 단기 조건이 다른 경우입니다.
        *   **RSI 70 이상 (과매수)**: 단기 급등으로 심리적 과열권에 진입해 언제든 이익실현 매물이 나올 수 있는 고점 구간입니다.
        *   **RSI 50 이하 (눌림목/일시 이탈)**: 상승 추세 속에서 일시적인 숨고르기나 거래량 감소로 단기 모멘텀이 죽어있는 국면입니다.
    *   **대응 전략**: 이미 보유 중이라면 **분할 익절**을 고려하고, 신규 진입의 경우 무리한 추격 매수를 자제하고 **눌림목 조정을 기다려 가격 메리트가 생길 때** 들어가는 것이 좋습니다.
    
    ### 3️⃣ 💤 관망 권장 (역배열 하락 추세 또는 횡보 소외)
    *   **정량적 기술 지표 기준**: 위의 상승 정배열 조건을 충족하지 못하는 모든 케이스 (`현재가 < 20일 이평선` 또는 `20일 이평선 < 60일 이평선` 등)
    *   **차트 해석**: 중장기 매물대가 머리 위에 얹어져 있는 하락 역배열 구간이거나, 거래량이 실리지 않아 방향성 없이 지루하게 기어가는 소외 국면입니다.
    *   **대응 전략**: 주가가 싸 보인다는 이유로 섣부르게 물타기를 하거나 진입하면 장기 소외될 위험이 큽니다. 추세 턴어라운드(골든크로스)가 확실히 확인될 때까지 **자금을 보존하며 관망**하는 것이 안전합니다.
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
if st.button("🚀 설정된 종목 실시간 전수 분석 시작", use_container_width=True):
    if not current_stocks_map:
        st.error("분석할 종목이 없습니다. 위의 편집창에 '종목명:종목코드' 형태로 입력되어 있는지 확인해 주세요.")
    else:
        group_success = []  # 📈 매수 긍정
        group_warning = []  # ⚠️ 진입 조율 필요
        group_info = []     # 💤 관망 권장
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_stocks = len(current_stocks_map)
        
        for idx, (name, code) in enumerate(current_stocks_map.items()):
            status_text.text(f"⏳ 데이터 연산 중 ({idx+1}/{total_stocks}): {name} ({code})")
            progress_bar.progress((idx + 1) / total_stocks)
            
            df = get_mobile_naver_data(code)
            if df.empty:
                time.sleep(0.1)
                df = get_mobile_naver_data(code)
                
            if not df.empty:
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
                
                # 정량적 수치에 입각한 3단계 분류 매칭
                is_trending = curr_price > ma20 > ma60
                is_momentum = 50 < curr_rsi < 70
                
                if is_trending and is_momentum:
                    group_success.append(stock_info)
                elif is_trending:
                    group_warning.append(stock_info)
                else:
                    group_info.append(stock_info)
                    
            time.sleep(0.04)
            
        status_text.text(f"✅ 총 {total_stocks}개 종목의 실시간 스크리닝이 완료되었습니다!")
        progress_bar.empty()
        
        # ==========================================
        # 3분할 대시보드 결과 출력
        # ==========================================
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.success(f"📈 매수 긍정 ({len(group_success)}개)")
            st.caption("상승 추세(정배열) + 적정 모멘텀 수치 진입")
            if group_success:
                st.dataframe(pd.DataFrame(group_success), use_container_width=True, hide_index=True)
            else:
                st.info("조건에 일치하는 종목이 없습니다.")
                
        with col2:
            st.warning(f"⚠️ 진입 조율 필요 ({len(group_warning)}개)")
            st.caption("상승세는 유지 중이나 과매수 구역이거나 추세 확인 필요")
            if group_warning:
                st.dataframe(pd.DataFrame(group_warning), use_container_width=True, hide_index=True)
            else:
                st.info("조건에 일치하는 종 info가 없습니다.")
                
        with col3:
            st.info(f"💤 관망 권장 ({len(group_info)}개)")
            st.caption("현재 하락 추세 구간이거나 박스권 횡보 중인 종목")
            if group_info:
                st.dataframe(pd.DataFrame(group_info), use_container_width=True, hide_index=True)
            else:
                st.info("조건에 일치하는 종목이 없습니다.")
