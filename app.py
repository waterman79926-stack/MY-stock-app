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

# 你可以隨時在這裡修改你的庫存股票代號（台股請加 .TW，例如 2330.TW）
my_stocks = st.sidebar.text_input(
    "輸入自選股代號（用逗號分隔）", 
    value="2330.TW, 2454.TW, 0050.TW, AAPL"
)
stock_list = [s.strip() for s in my_stocks.split(",")]

# 選擇技術指標參數
st.sidebar.subheader("📊 技術指標設定")
ma_fast = st.sidebar.number_input("快均線 (MA)", min_value=5, max_value=60, value=5)
ma_slow = st.sidebar.number_input("慢均線 (MA)", min_value=10, max_value=240, value=20)
rsi_period = st.sidebar.number_input("RSI 週期", min_value=5, max_value=30, value=14)

# --- 主畫面：核心資料處理與顯示 ---
if stock_list:
    # 讓使用者選擇目前要深入看哪一檔股票
    selected_stock = st.selectbox("選擇要檢視的股票", stock_list)
    
    st.subheader(f"🔍 {selected_stock} 詳細盤態分析")
    
    # 抓取資料（取最近一年的數據以利計算指標）
    @st.cache_data(ttl=60) # 快取資料 60 秒，避免頻繁抓取被鎖 IP
    def load_data(ticker):
        stock = yf.Ticker(ticker)
        # 抓取歷史 K 線
        df = stock.history(period="1y")
        # 抓取即時現價資訊
        info = stock.info
        return df, info

    try:
        df, info = load_data(selected_stock)
        
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
            # 均線 MA
            df['MA_fast'] = df['Close'].rolling(window=ma_fast).mean()
            df['MA_slow'] = df['Close'].rolling(window=ma_slow).mean()
            # RSI
            df['RSI'] = ta.momentum.rsi(df['Close'], window=rsi_period)
            # MACD
            macd_obj = ta.trend.MACD(df['Close'])
            df['MACD'] = macd_obj.macd()
            df['MACD_signal'] = macd_obj.macd_signal()
            df['MACD_diff'] = macd_obj.macd_diff()
            
            # 3. 繪製互動式 K 線圖 (包含均線)
            st.subheader("📈 互動式技術線圖")
            fig = gr.Figure()
            
            # K線
            fig.add_trace(gr.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name='K線'
            ))
            # 快慢均線
            fig.add_trace(gr.Scatter(x=df.index, y=df['MA_fast'], mode='lines', name=f'{ma_fast}MA', line=dict(width=1.5)))
            fig.add_trace(gr.Scatter(x=df.index, y=df['MA_slow'], mode='lines', name=f'{ma_slow}MA', line=dict(width=1.5)))
            
            fig.update_layout(xaxis_rangeslider_visible=False, height=500, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
            
            # 4. 顯示副指標 (RSI / MACD)
            col_rsi, col_macd = st.columns(2)
            
            with col_rsi:
                st.write(f"**RSI ({rsi_period}) 當前數值: {df['RSI'].iloc[-1]:.2f}**")
                fig_rsi = gr.Figure()
                fig_rsi.add_trace(gr.Scatter(x=df.index[-60:], y=df['RSI'].iloc[-60:], mode='lines', name='RSI', line=dict(color='purple')))
                fig_rsi.add_shape(type="line", x0=df.index[-60], y0=70, x1=df.index[-1], y1=70, line=dict(color="red", dash="dash"))
                fig_rsi.add_shape(type="line", x0=df.index[-60], y0=30, x1=df.index[-1], y1=30, line=dict(color="green", dash="dash"))
                fig_rsi.update_layout(height=250, margin=dict(t=0, b=0))
                st.plotly_chart(fig_rsi, use_container_width=True)
                
            with col_macd:
                st.write("**MACD 趨勢分析**")
                fig_macd = gr.Figure()
                fig_macd.add_trace(gr.Scatter(x=df.index[-60:], y=df['MACD'].iloc[-60:], name='MACD', line=dict(color='blue')))
                fig_macd.add_trace(gr.Scatter(x=df.index[-60:], y=df['MACD_signal'].iloc[-60:], name='Signal', line=dict(color='orange')))
                fig_macd.update_layout(height=250, margin=dict(t=0, b=0))
                st.plotly_chart(fig_macd, use_container_width=True)

            st.markdown("---")
            
            # 5. 每日買賣超與籌碼面說明
            st.subheader("👥 每日籌碼與三大法人買賣超說明")
            
            # 💡 技術限制補充說明
            st.info(
                "【籌碼資料說明】\n\n"
                "由於 Yahoo Finance (yfinance) 屬於國際免費開源 API，主要提供全球「價量」數據，"
                "並**未提供**台灣證券交易所（TWSE）的「三大法人買賣超明細」與「主力分點籌碼」。\n\n"
                "若要完美整合此功能，我們通常有兩種做法：\n"
                "1. **寫爬蟲**：每天盤後 15:00 自動去台灣證交所官網爬取 csv 檔並解析。\n"
                "2. **使用台灣在地 API**：例如使用 `FinMind` 或 `Fugle (富果)` 的 API 進行串接（部分需申請 Token）。"
            )
            
            # 提供一個當日數據概覽表格作為參考
            st.write("最後 5 日價量歷史數據：")
            st.dataframe(df[['Open', 'High', 'Low', 'Close', 'Volume']].tail(5).style.format("{:,.2f}"))

    except Exception as e:
        st.error(f"讀取資料時發生錯誤: {e}")
else:
    st.warning("請在側邊欄輸入至少一檔股票代號。")
