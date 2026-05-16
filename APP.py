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
# [신설] 화면 상단 배치: 3단계 판단 로직 상세 설명서
# ==========================================
st.markdown("### 📊 시스템 3단계 복합 판단 로직 설계서")
lead_col1, lead_col2, lead_col3 = st.columns(3)

with lead_col1:
    st.markdown("""
    <div style='background-color:#e8f5e9; padding:15px; border-radius:10px; border-left:5px solid #2e7d32;'>
        <h4 style='color:#2e7d32; margin-top:0;'>📈 1단계: 매수 긍정</h4>
        <p style='font-size:13px; margin-bottom:5px;'><b>주가 상태:</b> 중장기 정배열 우상향</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>기술 지표:</b> 현재가 > 20일선 > 60일선</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>수급/RSI:</b> 45 ≤ RSI ≤ 65 (과열 해소)</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>거래량 가중치:</b> 당일 수급 ≥ 5일 평균의 90%</p>
        <hr style='margin:10px 0;'>
        <p style='font-size:12px; color:#555;'><b>매매 전략:</b> 대세 상승장 속 기관·외인 수급이 동반된 가장 탄력적인 <b>안전 눌림목 및 돌파 타점</b>입니다. 적극적 분할 매수 진입이 유망합니다.</p>
    </div>
    """, unsafe_allow_html=True)

with lead_col2:
    st.markdown("""
    <div style='background-color:#fffde7; padding:15px; border-radius:10px; border-left:5px solid #fbc02d;'>
        <h4 style='color:#f57f17; margin-top:0;'>⚠️ 2단계: 진입 조율 필요</h4>
        <p style='font-size:13px; margin-bottom:5px;'><b>주가 상태:</b> 중장기 정배열은 유지 중</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>추세 이탈:</b> RSI > 65 (단기 과열 영역)</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>또는</b> RSI < 45 (단기 하락 심화)</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>또는</b> 당일 거래량 < 5일 평균의 90% (수급 공백)</p>
        <hr style='margin:10px 0;'>
        <p style='font-size:12px; color:#555;'><b>매매 전략:</b> 뼈대는 살아있으나 <b>단기 고점 과열이거나, 거래량이 메말라</b> 횡보 소외될 위험이 있습니다. 무리한 추격 매수를 자제하고 눌림목 확인 후 진입합니다.</p>
    </div>
    """, unsafe_allow_html=True)

with lead_col3:
    st.markdown("""
    <div style='background-color:#efebe9; padding:15px; border-radius:10px; border-left:5px solid #4e342e;'>
        <h4 style='color:#4e342e; margin-top:0;'>💤 3단계: 관망 권장</h4>
        <p style='font-size:13px; margin-bottom:5px;'><b>주가 상태:</b> 하락 추세 또는 역배열</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>기술 지표:</b> 현재가 < 20일선 또는 20일선 < 60일선</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>지표 상태:</b> 거래량 및 RSI 수치 무관 전람</p>
        <p style='font-size:13px; margin-bottom:5px;'><b>리스크:</b> 머리 위 장기 매물 저항 심화 상태</p>
        <hr style='margin:10px 0;'>
        <p style='font-size:12px; color:#555;'><b>매매 전략:</b> 주가가 저렴해 보이는 착시가 있으나 매물 벽이 두터워 <b>지하실을 파고 내려가거나 장기 소외</b>될 위험이 큽니다. 추세 전환 확인 시까지 철저히 관망합니다.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# 상단 컨트롤 타워: 내 마음대로 종목 편집창
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

st.info(f"📋 현재 설정된 분석 대상 종목: 총 **{len(current_stocks_map)}**개")

# ==========================================
# 메인 제어 분석 실행
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
            
            # 정량 보정형 3단계 로직 연산 매칭
            is_trending = curr_price > ma20 > ma60
            is_bullish_pullback = 45 <= curr_rsi <= 65
            is_volume_active = vol_ratio >= 0.9
            
            if is_trending and is_bullish_pullback and is_volume_active:
                success_list.append(stock_info)
            elif is_trending:
                warning_list.append(stock_info)
            else:
                info_list.append(stock_info)
        time.sleep(0.04)
    progress_bar.empty()
    st.session_state.screening_results = {"success": success_list, "warning": warning_list, "info": info_list}

# ==========================================
# 3분할 대시보드 결과 출력 및 인터랙티브 바인딩
# ==========================================
st.markdown("💡 **Tip**: 표 안에서 관심 있는 **종목의 행을 마우스로 클릭**하시면 하단에 실시간 이동평균선/RSI 결합 차트가 나타납니다.")
col1, col2, col3 = st.columns(3)

with col1:
    st.success(f"📈 매수 긍정 ({len(st.session_state.screening_results['success'])}개)")
    if st.session_state.screening_results['success']:
        df_suc = pd.DataFrame(st.session_state.screening_results['success'])
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
# 하단부: 차트 시각화 엔진
# ==========================================
if st.session_state.selected_stock_code:
    st.markdown("---")
    name = st.session_state.selected_stock_name
    code = st.session_state.selected_stock_code
    
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
            title=f"📈 {name} ({code}) 기술적 지표 결합 분석 차트",
            yaxis_title="주가 (원)", yaxis2_title="RSI",
            xaxis_rangeslider_visible=False, height=500,
            margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified"
        )
        fig.update_yaxes(range=[10, 90], row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)
