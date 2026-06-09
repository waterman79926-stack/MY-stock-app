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
import email.utils
import base64
import os

# 網頁基本設定與 CSS 注入
st.set_config(page_title="StockVision 智能台股戰情室", layout="wide", page_icon="📈")

# ==========================================
# 📊 資料載入優化 (只載入一次)
# ==========================================
api = DataLoader()

@st.cache_data(ttl=86400) 
def get_stock_names():
    try:
        df_info = api.taiwan_stock_info()
        # 建立名稱與代號的雙向映射
        return dict(zip(df_info['stock_id'].astype(str), df_info['stock_name'])), df_info
    except:
        return {}, pd.DataFrame()

name_dict, df_info_all = get_stock_names()

# ==========================================
# 📌 側邊欄：搜尋引擎修正
# ==========================================
st.sidebar.header("📌 戰情室控制台")

# 使用 session_state 來儲存目前的股票
if 'selected_stock' not in st.session_state:
    st.session_state.selected_stock = '2330'

# 改用單純的文字搜尋，配合下方按鈕過濾，最不容易壞
search_val = st.sidebar.text_input("🔍 搜尋股票代號或名稱", placeholder="輸入如: 2330, 鴻海")

if search_val:
    # 搜尋邏輯：代號或名稱包含關鍵字
    matches = df_info_all[df_info_all['stock_id'].str.contains(search_val) | 
                          df_info_all['stock_name'].str.contains(search_val)]
    
    if not matches.empty:
        st.sidebar.markdown("👉 **找到以下股票：**")
        for _, row in matches.head(10).iterrows():
            if st.sidebar.button(f"{row['stock_id']} {row['stock_name']}", use_container_width=True):
                st.session_state.selected_stock = str(row['stock_id'])
                st.rerun()
    else:
        st.sidebar.error("❌ 找不到相符的股票")

# 快捷按鈕區
st.sidebar.markdown("---")
st.sidebar.write("⚡ 常用自選股：")
quick_stocks = ["0050", "2330", "2317", "00878", "00981A", "0056"]
cols = st.sidebar.columns(3)
for stock in quick_stocks:
    if cols[quick_stocks.index(stock)%3].button(stock):
        st.session_state.selected_stock = stock
        st.rerun()

st.sidebar.markdown("---")
# 均線與區間設定... (簡略，邏輯與前版一致)
ma_fast = st.sidebar.number_input("快均線", value=5)
ma_slow = st.sidebar.number_input("慢均線", value=20)
timeframe = st.sidebar.radio("檢視區間", ["近一月", "近三月", "近半年", "近一年", "近五年"])

# ==========================================
# 🚀 顯示區塊 (增加數據回退機制)
# ==========================================
selected_stock = st.session_state.selected_stock
if selected_stock:
    # 抓資料
    df, divs, info = get_price_data(selected_stock)
    
    # 基本面資料 (FinMind 失敗時改顯示 N/A，不崩潰)
    pe_val, pb_val = "N/A", "N/A"
    try:
        f_data = api.taiwan_stock_per_pbr_and_dividend_yield(stock_id=selected_stock, start_date=(datetime.now()-timedelta(days=30)).strftime('%Y-%m-%d'))
        if not f_data.empty:
            pe_val = f"{f_data.iloc[-1].get('PER', 'N/A')}"
            pb_val = f"{f_data.iloc[-1].get('PBR', 'N/A')}"
    except:
        pass

    # 顯示... (其餘繪圖程式碼保持，確保變數 pe_val, pb_val 傳入)
    # ... (記得在metric中顯示)
