import streamlit as st
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET
import time
import re
import plotly.graph_objects as god  # 차트 시각화용 라이브러리 추가
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

# 세션 상태 초기화 (클릭한 종목 정보 저장용)
if 'selected_stock_code' not in st.session_state:
    st.session_state.selected_stock_code = None
if 'selected_stock_name' not in st.session_state:
    st.session_state.selected_stock_name = None

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
        
        # 날짜 포맷 변환 (YYYYMMDD -> YYYY-MM-DD)
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

def draw_stock_chart(name, code):
    """선택된 종목의 이동평균선 및 RSI 포함 캔들차트 생성"""
    df = get_mobile_naver_data(code, count=100)
    if df.empty:
        st.error("차트 데이터를 불러오지 못했습니다.")
        return

    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['RSI'] = calculate_rsi(df['Close'])

    # 주가 차트와 RSI 차트를 위아래 2단 분할 (비율 3:1)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])

    # 1. 메인 캔들스틱 차트 추가
    fig.add_trace(god.Candlestick(
        x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name='주가', increasing_line_color='#ef5350', decreasing_line_color='#26a69a'
    ), row=1, col=1)

    # 이평선 추가
    fig.add_trace(god.Scatter(x=df['Date'], y=df['MA20'], line=dict(color='#ff9800', width=1.5), name='20일선'), row=1, col=1)
    fig.add_trace(god.Scatter(x=df['Date'], y=df['MA60'], line=dict(color='#2196f3', width=1.5), name='60일선'), row=1, col=1)

    # 2. RSI 보조지표 추가
    fig.add_trace(god.Scatter(x=df['Date'], y=df['RSI'], line=dict(color='#9c27b0', width=1.5), name='RSI'), row=2, col=1)
    
    # RSI 기준선 과열(65), 침체(45/30) 점선 표기
    fig.add_hline(y=65, line_dash="dash", line_color="red", line_width=1, row=2, col=1)
    fig.add_hline(y=45, line_dash="dash", line_color="blue", line_width=1, row=2, col=1)

    # 차트 레이아웃 구성 개편
    fig.update_layout(
        title=f"📈 {name} ({code}) 실시간 기술적 분석 차트",
        yaxis_title="주가 (원)",
        yaxis2_title="RSI",
        xaxis_rangeslider_visible=False,
        height=550,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.update_yaxes(fixedrange=False, row=1, col=1)
    fig.update_yaxes(range=[10, 90], row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 메인 종목 세팅 및 스크리닝 컨트롤러
# ==========================================
with st.expander("🛠️ 분석 대상 종목 리스트 자유롭게 변경하기 (추가/삭제/수정)", expanded=False):
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

# 캐싱 시스템을 통한 연산 상태 보존
if 'screening_results' not in st.session_state:
    st.session_state.screening_results = {"success": [], "warning": [], "info": []}

if st.button("🚀 종합 복합 스크리닝 전수 분석 시작", use_container_width=True):
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
    st.session_state.screening_results = {"success": success_list, "warning": warning_list, "info": info_list}

# ==========================================
# 3분할 데이터프레임 노출 및 선택 이벤트 연동
# ==========================================
st.markdown("---")
st.markdown("💡 **Tip**: 아래 표에서 관심 있는 **종목의 행을 마우스로 클릭**하시면, 페이지 하단에 해당 종목의 실시간 기술적 분석 차트가 즉시 연동되어 나타납니다.")

col1, col2, col3 = st.columns(3)

with col1:
    st.success(f"📈 매수 긍정 ({len(st.session_state.screening_results['success'])}개)")
    if st.session_state.screening_results['success']:
        df_suc = pd.DataFrame(st.session_state.screening_results['success'])
        # Streamlit 최신기능인 선택 이벤트(on_select) 캡처
        sel_suc = st.dataframe(df_suc, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")
        if sel_suc.selection.rows:
            selected_row = sel_suc.selection.rows[0]
            st.session_state.selected_stock_name = df_suc.iloc[selected_row]['종목명']
            st.session_state.selected_stock_code = df_suc.iloc[selected_row]['종목코드']

with col2:
    st.warning(f"⚠️ 진입 조율 필요 ({len(st.session_state.screening_results['warning'])}개)")
    if st.session_state.screening_results['warning']:
        df_war = pd.DataFrame(st.session_state.screening_results['warning'])
        sel_war = st.dataframe(df_war, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")
        if sel_war.selection.rows:
            selected_row = sel_war.selection.rows[0]
            st.session_state.selected_stock_name = df_war.iloc[selected_row]['종목명']
            st.session_state.selected_stock_code = df_war.iloc[selected_row]['종목코드']

with col3:
    st.info(f"💤 관망 권장 ({len(st.session_state.screening_results['info'])}개)")
    if st.session_state.screening_results['info']:
        df_inf = pd.DataFrame(st.session_state.screening_results['info'])
        sel_inf = st.dataframe(df_inf, use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun")
        if sel_inf.selection.rows:
            selected_row = sel_inf.selection.rows[0]
            st.session_state.selected_stock_name = df_inf.iloc[selected_row]['종목명']
            st.session_state.selected_stock_code = df_inf.iloc[selected_row]['종목코드']

# ==========================================
# 하단부: 선택된 종목 인터랙티브 차트 디스플레이
# ==========================================
if st.session_state.selected_stock_code:
    st.markdown("---")
    draw_stock_chart(st.session_state.selected_stock_name, st.session_state.selected_stock_code)
