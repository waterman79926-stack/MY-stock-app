import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as gr
from datetime import datetime, timedelta

# 網頁基本設定
st.set_page_config(page_title="我的專屬持股即時監控面板", layout="wide")
st.title("📈 我的專屬持股即時監控面板")

# --- 側邊欄：設定你的持股清單 ---
st.sidebar.header("📌 持股設定與參數")

# 調整後的預設值，直接用你習慣的純數字與美股代號
my_stocks = st.sidebar.text_input(
    "輸入自選股代號（用逗號分隔）", 
    value="2330, 0050, 00923, 00713, 00878, 00981A"
)

# 【核心優化】自動判斷台股並補上 .TW
raw_stock_list = [s.strip() for s in my_stocks.split(",")]
stock_list = []
display_mapping = {}  # 用來讓下拉選單顯示乾淨名稱的對照表

for s in raw_stock_list:
    if s:
        # 如果輸入的是純數字（代表台股），背後自動補上 .TW
        if s.isdigit():
            api_ticker = f"{s}.TW"
        else:
            api_ticker = s
        
        stock_list.append(api_ticker)
        display_mapping[api_ticker] = s  # 記錄原本對稱的名稱

# 選擇技術指標參數
st.sidebar.subheader("📊 技術指標設定")
ma_fast = st.sidebar.number_input("快均線 (MA)", min_value=5, max_value=60, value=5)
ma_slow = st.sidebar.number_input("慢均線 (MA)", min_value=10, max_value=240, value=20)
rsi_period = st.sidebar.number_input("RSI 週期", min_value=5, max_value=30, value=14)

# --- 主畫面：核心資料處理與顯示 ---
if stock_list:
    # 下拉選單顯示原本乾淨的代號（例如 2330），但背後對應 api_ticker
    selected_ticker = st.selectbox(
        "選擇要檢視的股票", 
        options=stock_list, 
        format_func=lambda x: display_mapping.get(x, x)
    )
    
    st.subheader(f"🔍 {display_mapping.get(selected_ticker, selected_ticker)} 詳細盤態分析")
    
    # 抓取資料
    @st.cache_data(ttl=60)
    def load_data(ticker):
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y")
        info = stock.info
        return df, info

    try:
        df, info = load_data(selected_ticker)
        
        if df.empty:
            st.error("找不到該股票資料，請檢查代號是否正確。")
        else:
            # 1. 顯示即時重點數據
            current_price = info.get('regularMarketPrice', df['Close'].iloc[-1])
            prev_close = info.get('regularMarketPreviousClose', df['Close'].iloc[-2])
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close) * 100
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("即時股價", f"${current_price:.2f}", f"{price_change:+.2f} ({price_change_pct:+.2f}%)")
            col2.metric("今日最高", f"${df['High'].iloc[-1]:.2f}")
            col3.metric("今日最低", f"${df['Low'].iloc[-1]:.2f}")
            col4.metric("成交量", f"{df['Volume'].iloc[-1]:,}")
            
            st.markdown("---")
            
            # 2. 計算技術指標
            df['MA_fast'] = df['Close'].rolling(window=ma_fast).mean()
            df['MA_slow'] = df['Close'].rolling(window=ma_slow).mean()
            df['RSI'] = ta.momentum.rsi(df['Close'], window=rsi_period)
            
            # 3. 繪製互動式 K 線圖
            st.subheader("📈 互動式技術線圖")
            fig = gr.Figure()
            
            fig.add_trace(gr.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name='K線',
                increasing_line_color='red', increasing_fill_color='red', # 符合台股紅漲綠跌習慣
                decreasing_line_color='green', decreasing_fill_color='green'
            ))
            fig.add_trace(gr.Scatter(x=df.index, y=df['MA_fast'], mode='lines', name=f'{ma_fast}MA', line=dict(width=1.5)))
            fig.add_trace(gr.Scatter(x=df.index, y=df['MA_slow'], mode='lines', name=f'{ma_slow}MA', line=dict(width=1.5)))
            
            fig.update_layout(xaxis_rangeslider_visible=False, height=500, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
            
            # 4. 顯示 RSI 指標
            st.write(f"**RSI ({rsi_period}) 當前數值: {df['RSI'].iloc[-1]:.2f}**")
            fig_rsi = gr.Figure()
            fig_rsi.add_trace(gr.Scatter(x=df.index[-60:], y=df['RSI'].iloc[-60:], mode='lines', name='RSI', line=dict(color='purple')))
            fig_rsi.add_shape(type="line", x0=df.index[-60], y0=70, x1=df.index[-1], y1=70, line=dict(color="red", dash="dash"))
            fig_rsi.add_shape(type="line", x0=df.index[-60], y0=30, x1=df.index[-1], y1=30, line=dict(color="green", dash="dash"))
            fig_rsi.update_layout(height=200, margin=dict(t=0, b=0))
            st.plotly_chart(fig_rsi, use_container_width=True)

            st.markdown("---")
            st.write("最後 5 日價量歷史數據：")
            st.dataframe(df[['Open', 'High', 'Low', 'Close', 'Volume']].tail(5).style.format("{:,.2f}"))

    except Exception as e:
        st.error(f"讀取資料時發生錯誤: {e}")
else:
    st.warning("請在側邊欄輸入至少一檔股票代號。")
