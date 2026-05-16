import streamlit as st
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET
import re

# 웹 페이지 설정
st.set_page_config(page_title="하이모바일 주식 분석기", layout="wide")

st.title("📈 네이버 금융 연동 상승 모멘텀 분석기")
st.sidebar.header("설정")

# 사용자가 직접 한국 주식 종목코드 입력
target_stocks = st.sidebar.text_input("분석할 종목 코드를 입력하세요 (쉼표 구분)", "005930, 000660, 005380, 000270, 066570")
tickers = [t.strip() for t in target_stocks.split(",")]

@st.cache_data
def get_krx_stock_map():
    """1차 안전장치: 한국거래소 마스터 데이터"""
    try:
        url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
        df_krx = pd.read_html(url, header=0)[0]
        df_krx['종목코드'] = df_krx['종목코드'].astype(str).str.zfill(6)
        return dict(zip(df_krx['종목코드'], df_krx['회사명']))
    except Exception:
        return {}

def get_company_name_from_naver(code):
    """2차 안전장치 [정밀 보완]: 타이틀 매칭 오류를 잡고 메타 태그에서 순수 회사명만 추출합니다."""
    try:
        url = f"https://m.stock.naver.com/domestic/stock/{code}/total"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G960N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Mobile Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        
        # [정밀 수정] HTML의 공유용 메타 태그(og:title)에서 순수 회사명만 추출
        # 예시 구조: <meta property="og:title" content="삼성전자"/>
        meta_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', response.text, re.IGNORECASE)
        if meta_match:
            clean_name = meta_match.group(1).strip()
            # 포괄적인 정제 작업 (혹시나 뒤에 붙을 군더더기 제거)
            clean_name = clean_name.split(':')[0].split('-')[0].strip()
            if clean_name and "네이버" not in clean_name and "페이지를" not in clean_name:
                return clean_name
                
        # 만약 메타 태그 실패 시 기존 타이틀 방식의 예외 처리 강화
        title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
        if title_match:
            raw_title = title_match.group(1).strip()
            # "Npay 증권", "네이버페이 증권" 문자열 자체를 통째로 도려냄
            clean_name = re.sub(r'[:\-\|]?\s*네이버페이\s*증권|\s*Npay\s*증권', '', raw_title, flags=re.IGNORECASE).strip()
            if clean_name:
                return clean_name
    except Exception:
        pass
    
    # 3차 안전장치: 대형주 백업 맵
    backup_map = {
        "005930": "삼성전자", "000660": "SK하이닉스", "005380": "현대차", 
        "000270": "기아", "012330": "현대모비스", "066570": "LG전자",
        "035720": "카카오", "035420": "NAVER", "005490": "POSCO홀딩스"
    }
    return backup_map.get(code, f"종목({code})")

# 거래소 데이터 맵 로드
krx_map = get_krx_stock_map()

def get_naver_stock_data(code, count=100):
    """네이버 금융에서 일별 시세를 가져오는 함수"""
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count={count}&requestType=0"
    try:
        response = requests.get(url)
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
    """RSI 계산 수식"""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

# 분석 실행
if st.sidebar.button("네이버 데이터 분석 시작"):
    for ticker in tickers:
        clean_ticker = ''.join(filter(str.isdigit, ticker))
        if len(clean_ticker) < 6:
            clean_ticker = clean_ticker.zfill(6)
        
        # 이름 가져오기 프로세스
        stock_name = krx_map.get(clean_ticker)
        if not stock_name:
            stock_name = get_company_name_from_naver(clean_ticker)
        
        with st.container():
            st.subheader(f"🔍 {stock_name} ({clean_ticker}) 분석 결과")
            
            # 데이터 수집
            df = get_naver_stock_data(clean_ticker)
            if df.empty:
                st.error(f"[{stock_name}] 데이터를 불러오지 못했습니다. 코드를 확인해 주세요.")
                continue

            # 기술적 지표 계산
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA60'] = df['Close'].rolling(window=60).mean()
            df['RSI'] = calculate_rsi(df['Close'])

            curr_price = df['Close'].iloc[-1]
            curr_rsi = df['RSI'].iloc[-1]
            ma20 = df['MA20'].iloc[-1]
            ma60 = df['MA60'].iloc[-1]

            # 대시보드 화면 표시
            m1, m2 = st.columns(2)
            m1.metric("현재가 (원)", f"{curr_price:,.0f}")
            m2.metric("RSI 지수", f"{curr_rsi:.2f}")

            # 차트 시각화
            st.line_chart(df[['Close', 'MA20', 'MA60']])
            
            # 모멘텀 판단 로직
            is_trending = curr_price > ma20 > ma60
            is_momentum = 50 < curr_rsi < 70
            
            if is_trending and is_momentum:
                st.success(f"✅ {stock_name}: 상승 모멘텀 포착 (매수 긍정)")
            elif is_trending:
                st.warning(f"⚠️ {stock_name}: 안정적인 정배열 상승 추세이나, 진입 시점 조율 필요")
            else:
                st.info(f"{stock_name}: 현재 하락 추세이거나 횡보 구간입니다. 관망을 권장합니다.")
            st.divider()
