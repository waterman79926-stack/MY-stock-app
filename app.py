import streamlit as st
import pandas as pd
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
import yfinance as yf
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import quote
import base64
import os

# 網頁基礎設定
st.set_page_config(page_title="StockVision 智能台股戰情室", layout="wide", page_icon="📈")

#  CSS 樣式定義
st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; }
    .landing-title { font-size: 3rem; font-weight: 800; background: linear-gradient(45deg, #ff4b4b, #ff904f); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    </style>
""", unsafe_allow_html=True)

# 顯示 Logo 與標題
def get_logo_html():
    for filename in ["logo.png.jpg", "logo.png"]:
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return f'<img src="data:image/jpeg;base64,{b64}" width="55" style="margin-right: 15px; border-radius: 50%; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">'
    return "📈"

st.markdown(f"""
    <div style="display: flex; align-items: center; margin-bottom: 0.8rem; margin-top: -10px;">
        {get_logo_html()}
        <h2 style="margin: 0;">StockVision 智能台股戰情室</h2>
    </div>
""", unsafe_allow_html=True)

# 初始化資料載入器
api = DataLoader()

@st.cache_data(ttl=86400) 
def get_stock_info():
    try:
        df = api.taiwan_stock_info()
        return df.set_index('stock_id').to_dict('index')
    except: return {}

info_dict = get_stock_info()

# 側邊欄控制台
if 'selected_stock' not in st.session_state: st.session_state.selected_stock = ''

st.sidebar.header("📌 控制台")
search = st.sidebar.text_input("🔍 搜尋代號/名稱", placeholder="輸入如: 2330")

if search:
    matches = {sid: data for sid, data in info_dict.items() if search in sid or search in data.get('stock_name', '')}
    for sid, data in list(matches.items())[:10]:
        if st.sidebar.button(f"{sid} {data.get('stock_name', '')}"):
            st.session_state.selected_stock = sid
            st.rerun()

# 數據獲取模組 (包含上市櫃自動跳轉與防呆)
@st.cache_data(ttl=300)
def get_data(sid):
    # 嘗試上市或上櫃抓取價格
    for s in [".TW", ".TWO"]:
        try:
            ticker = yf.Ticker(f"{sid}{s}")
            df = ticker.history(period="5y")
            if not df.empty: return df, ticker.dividends, ticker.info
        except: continue
    return pd.DataFrame(), pd.Series(), {}

# 主內容區
if st.session_state.selected_stock:
    sid = st.session_state.selected_stock
    df, divs, info = get_data(sid)
    
    if df.empty:
        st.error("無法取得該股票資料，請檢查代號。")
    else:
        # 計算指標
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        
        # 顯示指標卡片
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("最新收盤", f"${df['Close'].iloc[-1]:.2f}")
        col2.metric("本益比", info.get('trailingPE', 'N/A'))
        col3.metric("產業類別", info.get('sector', 'N/A'))
        col4.metric("每股盈餘(EPS)", info.get('trailingEps', 'N/A'))
        
        # 繪圖
        fig = gr.Figure(data=[gr.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        st.plotly_chart(fig, use_container_width=True)
else:
    st.markdown('<div class="landing-title">洞悉主力籌碼，精準打擊獲利。</div>', unsafe_allow_html=True)
    st.write("請從左側搜尋股票代號開始使用。")
