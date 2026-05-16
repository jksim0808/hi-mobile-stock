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
# 상단 컨트롤 타워: 내 마음대로 종목 편집창
# ==========================================
with st.expander("🛠️ 분석 대상 종목 리스트 자유롭게 변경하기 (추가/삭제/수정)", expanded=True):
    st.markdown("**형식 가이드**: `종목명:6자리코드` 형태로 작성하고, 각 종목은 **쉼표(,)나 줄바꿈(엔터)**으로 구분해 주세요.")
    
    # 사용자가 직접 편집할 수 있는 대형 텍스트 편집기 제공
    user_stocks_input = st.text_area(
        "현재 분석 대상 리스트 (원하는 대로 지우거나 추가해 보세요)",
        value=DEFAULT_STOCKS_TEXT,
        height=150
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

# 현재 유효하게 파싱된 종목 개수 표시
st.info(f"📋 현재 설정된 분석 대상 종목: 총 **{len(current_stocks_map)}**개")

# ==========================================
# 메인 제어 분석 실행
# ==========================================
if st.button("🚀 설정된 종목 실시간 전수 분석 시작", use_container_width=True):
    if not current_stocks_map:
        st.error("분석할 종목이 없습니다. 위의 편집창에 '종목명:종목코드' 형태로 입력되어 있는지 확인해 주세요.")
    else:
        # 결과를 담을 3가지 분류 리스트
        group_success = []  # 📈 상승 모멘텀 포착 (매수 긍정)
        group_warning = []  # ⚠️ 정배열 상승세 (진입 조율 필요)
        group_info = []     # 💤 관망 구간 (하락 추세 또는 횡보)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_stocks = len(current_stocks_map)
        
        # 동적으로 구성된 종목 셋 순회 분석
        for idx, (name, code) in enumerate(current_stocks_map.items()):
            status_text.text(f"⏳ 데이터 연산 중 ({idx+1}/{total_stocks}): {name} ({code})")
            progress_bar.progress((idx + 1) / total_stocks)
            
            df = get_mobile_naver_data(code)
            if df.empty:
                time.sleep(0.1)
                df = get_mobile_naver_data(code) # 실패 시 1회 우회 재시도
                
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
                
                # 3단계 판단 로직
                is_trending = curr_price > ma20 > ma60
                is_momentum = 50 < curr_rsi < 70
                
                if is_trending and is_momentum:
                    group_success.append(stock_info)
                elif is_trending:
                    group_warning.append(stock_info)
                else:
                    group_info.append(stock_info)
                    
            time.sleep(0.04) # 서버 과부하 방지 가벼운 마진
            
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
                st.info("조건에 일치하는 종목이 없습니다.")
                
        with col3:
            st.info(f"💤 관망 권장 ({len(group_info)}개)")
            st.caption("현재 하락 추세 구간이거나 박스권 횡보 중인 종목")
            if group_info:
                st.dataframe(pd.DataFrame(group_info), use_container_width=True, hide_index=True)
            else:
                st.info("조건에 일치하는 종목이 없습니다.")
