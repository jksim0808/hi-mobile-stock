import streamlit as st
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET
import time
import re
import plotly.graph_objects as god
from plotly.subplots import make_subplots

# 모바일 화면 최적화 및 와이드 레이아웃 설정
st.set_page_config(page_title="하이모바일 주식 매니저", layout="wide")

st.title("📊 하이모바일 커스텀 주식 스크리닝 매니저")
st.caption("추세 + RSI + 거래량 통합 스크리닝 및 인터랙티브 차트 연동 시스템")

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

# ==========================================
# ⚠️ 핵심 보정: 세션 상태(메모리) 구조 최적화
# ==========================================
if 'selected_stock_code' not in st.session_state:
    st.session_state.selected_stock_code = None
if 'selected_stock_name' not in st.session_state:
    st.session_state.selected_stock_name = None
if 'screening_results' not in st.session_state:
    st.session_state.screening_results = {"success": [], "warning": [], "info": []}

def get_mobile_naver_data(code, count=100):
    """네이버 금융 피드에서 주가 및 거래량 데이터 추출"""
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
        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
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
# 시스템 3단계 복합 판단 로직 설계서
# ==========================================
st.markdown("### 📊 시스템 3단계 복합 판단 로직 설계서")
lead_col1, lead_col2, lead_col3 = st.columns(3)

with lead_col1:
    st.markdown("""
    <div style='background-color:#e8f5e9; padding:15px; border-radius:10px; border-left:5px solid #2e7d32;'>
        <h4 style='color:#2e7d32; margin-top:0;'>📈 1단계: 매수 긍정</h4>
        <p style='font-size:13px; margin-bottom:5px;'><b>기술 지표:</b> 현재가 > 20일선 > 60일선</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>수급/RSI:</b> 45 ≤ RSI ≤ 65 (안전지대)</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>거래량 비율:</b> 당일 수급 ≥ 5일 평균의 90%</p>
    </div>
    """, unsafe_allow_html=True)

with lead_col2:
    st.markdown("""
    <div style='background-color:#fffde7; padding:15px; border-radius:10px; border-left:5px solid #fbc02d;'>
        <h4 style='color:#f57f17; margin-top:0;'>⚠️ 2단계: 진입 조율 필요</h4>
        <p style='font-size:13px; margin-bottom:5px;'><b>추세 상태:</b> 중장기 정배열은 유지 중</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>제한 요소:</b> RSI 과열(>65) 또는 거래량 부족(<90%)</p>
    </div>
    """, unsafe_allow_html=True)

with lead_col3:
    st.markdown("""
    <div style='background-color:#efebe9; padding:15px; border-radius:10px; border-left:5px solid #4e342e;'>
        <h4 style='color:#4e342e; margin-top:0;'>💤 3단계: 관망 권장</h4>
        <p style='font-size:13px; margin-bottom:5px;'><b>추세 상태:</b> 하락 추세 또는 이평선 역배열</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>리스크:</b> 머리 위 두터운 매물 저항 압력 존재</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# 종목 리스트 입력창
# ==========================================
with st.expander("🛠️ 분석 대상 종목 리스트 자유롭게 변경하기", expanded=False):
    user_stocks_input = st.text_area("현재 분석 대상 리스트", value=DEFAULT_STOCKS_TEXT, height=100)

current_stocks_map = {}
raw_items = re.split(r'[,\n]', user_stocks_input)
for item in raw_items:
    if ":" in item:
        name_part, code_part = item.split(":", 1)
        clean_name = name_part.strip()
        clean_code = ''.join(filter(str.isdigit, code_part)).zfill(6)
        if clean_name and len(clean_code) == 6:
            current_stocks_map[clean_name] = clean_code

# ==========================================
# 분석 실행 엔진
# ==========================================
if st.button("🚀 설정된 종목 실시간 보정형 전수 분석 시작", use_container_width=True):
    success_list, warning_list, info_list = [], [], []
    progress_bar = st.progress(0)
    total_stocks = len(current_stocks_map)
    
    for idx, (name, code) in enumerate(current_stocks_map.items()):
        progress_bar.progress((idx + 1) / total_stocks)
        df = get_mobile_naver_data(code)
        if not df.empty:
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA60'] = df['Close'].rolling(window=60).mean()
            df['RSI'] = calculate_rsi(df['Close'])
            df['Vol_MA5'] = df['Volume'].shift(1).rolling(window=5).mean()
            
            curr_price = int(df['Close'].iloc[-1])
            curr_rsi = float(df['RSI'].iloc[-1])
            ma20 = float(df['MA20'].iloc[-1])
            ma60 = float(df['MA60'].iloc[-1])
            curr_vol = float(df['Volume'].iloc[-1])
            vol_ma5 = float(df['Vol_MA5'].iloc[-1]) if not pd.isna(df['Vol_MA5'].iloc[-1]) else 0.0
            
            vol_ratio = curr_vol / vol_ma5 if vol_ma5 > 0 else 0.0
            
            stock_info = {
                "종목명": name, "종목코드": code, "현재가": curr_price,
                "RSI": round(curr_rsi, 1), "거래량비율": f"{vol_ratio * 100:.1f}%"
            }
            
            if curr_price > ma20 > ma60 and 45 <= curr_rsi <= 65 and vol_ratio >= 0.9:
                success_list.append(stock_info)
            elif curr_price > ma20 > ma60:
                warning_list.append(stock_info)
            else:
                info_list.append(stock_info)
        time.sleep(0.04)
    progress_bar.empty()
    
    # 분석이 새로 실행되면 기존 차트 선택 상태는 초기화하되 데이터는 갱신
    st.session_state.screening_results = {"success": success_list, "warning": warning_list, "info": info_list}

# ==========================================
# ⚠️ 변경점: 독립적인 데이터프레임 이벤트 처리 연동
# ==========================================
st.markdown("💡 **Tip**: 표 안에서 관심 있는 **종목의 행을 마우스로 클릭**하시면 하단에 실시간 분석 차트가 즉시 연동됩니다.")
col1, col2, col3 = st.columns(3)

with col1:
    st.success(f"📈 매수 긍정 ({len(st.session_state.screening_results['success'])}개)")
    if st.session_state.screening_results['success']:
        df_suc = pd.DataFrame(st.session_state.screening_results['success'])
        sel_suc = st.dataframe(df_suc, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")
        # 선택 이벤트 발생 시 세션 고정 강제 주입
        if sel_suc.selection.rows:
            st.session_state.selected_stock_name = df_suc.iloc[sel_suc.selection.rows[0]]['종목명']
            st.session_state.selected_stock_code = df_suc.iloc[sel_suc.selection.rows[0]]['종목코드']

with col2:
    st.warning(f"⚠️ 진입 조율 필요 ({len(st.session_state.screening_results['warning'])}개)")
    if st.session_state.screening_results['warning']:
        df_war = pd.DataFrame(st.session_state.screening_results['warning'])
        sel_war = st.dataframe(df_war, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")
        if sel_war.selection.rows:
            st.session_state.selected_stock_name = df_war.iloc[sel_war.selection.rows[0]]['종목명']
            st.session_state.selected_stock_code = df_war.iloc[sel_war.selection.rows[0]]['종목코드']

with col3:
    st.info(f"💤 관망 권장 ({len(st.session_state.screening_results['info'])}개)")
    if st.session_state.screening_results['info']:
        df_inf = pd.DataFrame(st.session_state.screening_results['info'])
        sel_inf = st.dataframe(df_inf, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")
        if sel_inf.selection.rows:
            st.session_state.selected_stock_name = df_inf.iloc[sel_inf.selection.rows[0]]['종목명']
            st.session_state.selected_stock_code = df_inf.iloc[sel_inf.selection.rows[0]]['종목코드']

# ==========================================
# 하단부: 차트 시각화 출력 (독립 작동)
# ==========================================
if st.session_state.selected_stock_code:
    st.markdown("---")
    name = st.session_state.selected_stock_name
    code = st.session_state.selected_stock_code
    
    # 현재 선택된 종목 표시 헤더 및 선택 해제 버튼 추가
    c_left, c_right = st.columns([0.85, 0.15])
    with c_left:
        st.subheader(f"📊 현재 선택된 차트: {name} ({code})")
    with c_right:
        if st.button("❌ 차트 닫기", use_container_width=True):
            st.session_state.selected_stock_code = None
            st.session_state.selected_stock_name = None
            st.rerun()
            
    if st.session_state.selected_stock_code:
        df_chart = get_mobile_naver_data(code, count=100)
        if not df_chart.empty:
            df_chart['MA20'] = df_chart['Close'].rolling(window=20).mean()
            df_chart['MA60'] = df_chart['Close'].rolling(window=60).mean()
            df_chart['RSI'] = calculate_rsi(df_chart['Close'])

            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
            fig.add_trace(god.Candlestick(
                x=df_chart['Date'], open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'],
                name='주가', increasing_line_color='#ef5350', decreasing_line_color='#26a69a'
            ), row=1, col=1)

            fig.add_trace(god.Scatter(x=df_chart['Date'], y=df_chart['MA20'], line=dict(color='#ff9800', width=1.5), name='20일선'), row=1, col=1)
            fig.add_trace(god.Scatter(x=df_chart['Date'], y=df_chart['MA60'], line=dict(color='#2196f3', width=1.5), name='60일선'), row=1, col=1)
            fig.add_trace(god.Scatter(x=df_chart['Date'], y=df_chart['RSI'], line=dict(color='#9c27b0', width=1.5), name='RSI'), row=2, col=1)
            
            fig.add_hline(y=65, line_dash="dash", line_color="red", line_width=1, row=2, col=1)
            fig.add_hline(y=45, line_dash="dash", line_color="blue", line_width=1, row=2, col=1)

            fig.update_layout(
                yaxis_title="주가 (원)", yaxis2_title="RSI",
                xaxis_rangeslider_visible=False, height=500,
                margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified"
            )
            fig.update_yaxes(range=[10, 90], row=2, col=1)
            st.plotly_chart(fig, use_container_width=True)
