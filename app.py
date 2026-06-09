import streamlit as st
import pandas as pd
import plotly.graph_objects as gr
import yfinance as yf
from FinMind.data import DataLoader
from datetime import datetime, timedelta

# 網頁基本設定
st.set_page_config(page_title="我的專屬持股即時監控面板", layout="wide")
st.title("📈 我的專屬持股即時監控面板")

# 初始化 FinMind (用來抓法人資料與股票名稱)
api = DataLoader()

# --- 取得台股代號與中文名稱對照表 ---
@st.cache_data(ttl=86400) # 快取 24 小時
def get_stock_names():
    try:
        df_info = api.taiwan_stock_info()
        # 建立 dict: {'2330': '台積電', '0050': '元大台灣50', ...}
        return dict(zip(df_info['stock_id'], df_info['stock_name']))
    except:
        return {}

name_dict = get_stock_names()

# --- 側邊欄：設定清單與參數 ---
st.sidebar.header("📌 持股設定與參數")

my_stocks = st.sidebar.text_input(
    "輸入自選股代號（用逗號分隔）", 
    value="2330, 0050, 2454, 2317, 00878"
)
stock_list = [s.strip() for s in my_stocks.split(",") if s.strip()]

st.sidebar.subheader("📊 均線參數設定")
ma_fast = st.sidebar.number_input("快均線 (MA)", min_value=5, max_value=60, value=5)
ma_slow = st.sidebar.number_input("慢均線 (MA)", min_value=10, max_value=240, value=20)

end_date = datetime.today().strftime('%Y-%m-%d')
start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')

# --- 主畫面 ---
if stock_list:
    selected_stock = st.selectbox("選擇要檢視的股票", stock_list)
    
    # 取得中文名稱
    stock_chinese_name = name_dict.get(selected_stock, "")
    display_title = f"{selected_stock} {stock_chinese_name}" if stock_chinese_name else selected_stock
    
    st.subheader(f"🔍 {display_title} 詳細盤態分析")
    
    # 1. 抓取精準股價 (使用 yfinance)
    @st.cache_data(ttl=300) 
    def get_price_data(stock_id):
        # 先嘗試上市 (.TW)
        ticker = yf.Ticker(f"{stock_id}.TW")
        df = ticker.history(period="6mo")
        if df.empty:
            # 如果空的，嘗試上櫃 (.TWO)
            ticker = yf.Ticker(f"{stock_id}.TWO")
            df = ticker.history(period="6mo")
        
        if not df.empty:
            df.index = df.index.tz_localize(None) # 移除時區，方便畫圖
        return df

    # 2. 抓取法人籌碼 (使用 FinMind)
    @st.cache_data(ttl=300)
    def get_inst_data(stock_id, start, end):
        try:
            return api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start, end_date=end)
        except:
            return pd.DataFrame()

    with st.spinner("資料讀取中..."):
        df_price = get_price_data(selected_stock)
        df_inst = get_inst_data(selected_stock, start_date, end_date)

    if df_price.empty:
        st.error("找不到該股票的歷史價格，請確認代號是否正確。")
    else:
        # ==========================================
        # 📊 重點數據顯示
        # ==========================================
        current_price = df_price['Close'].iloc[-1]
        prev_close = df_price['Close'].iloc[-2] if len(df_price) > 1 else current_price
        price_change = current_price - prev_close
        price_change_pct = (price_change / prev_close) * 100 if prev_close != 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("最新收盤價", f"${current_price:.2f}", f"{price_change:+.2f} ({price_change_pct:+.2f}%)")
        col2.metric("今日最高", f"${df_price['High'].iloc[-1]:.2f}")
        col3.metric("今日最低", f"${df_price['Low'].iloc[-1]:.2f}")
        col4.metric("成交張數", f"{int(df_price['Volume'].iloc[-1] / 1000):,} 張")
        
        st.markdown("---")

        # ==========================================
        # 🧮 計算技術指標
        # ==========================================
        df_price['MA_fast'] = df_price['Close'].rolling(window=ma_fast).mean()
        df_price['MA_slow'] = df_price['Close'].rolling(window=ma_slow).mean()
        
        # 布林通道
        df_price['STD20'] = df_price['Close'].rolling(window=20).std()
        df_price['BB_upper'] = df_price['MA_slow'] + (df_price['STD20'] * 2)
        df_price['BB_lower'] = df_price['MA_slow'] - (df_price['STD20'] * 2)

        # RSI (14日)
        delta = df_price['Close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df_price['RSI'] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = df_price['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df_price['Close'].ewm(span=26, adjust=False).mean()
        df_price['MACD'] = exp1 - exp2
        df_price['MACD_signal'] = df_price['MACD'].ewm(span=9, adjust=False).mean()
        df_price['MACD_diff'] = df_price['MACD'] - df_price['MACD_signal']

        # ==========================================
        # 📈 1. 繪製主 K 線圖
        # ==========================================
        st.subheader("📈 主圖：互動 K 線圖與布林通道")
        fig = gr.Figure()
        
        fig.add_trace(gr.Candlestick(
            x=df_price.index, open=df_price['Open'], high=df_price['High'], low=df_price['Low'], close=df_price['Close'],
            name='K線',
            increasing=dict(line=dict(color='#ff3333'), fillcolor='#ff3333'),
            decreasing=dict(line=dict(color='#00b33c'), fillcolor='#00b33c')
        ))
        fig.add_trace(gr.Scatter(x=df_price.index, y=df_price['MA_fast'], mode='lines', name=f'{ma_fast}MA', line=dict(width=1.5, color='orange')))
        fig.add_trace(gr.Scatter(x=df_price.index, y=df_price['MA_slow'], mode='lines', name=f'{ma_slow}MA', line=dict(width=1.5, color='blue')))
        fig.add_trace(gr.Scatter(x=df_price.index, y=df_price['BB_upper'], mode='lines', name='布林上軌', line=dict(width=1, color='rgba(150, 150, 150, 0.5)', dash='dash')))
        fig.add_trace(gr.Scatter(x=df_price.index, y=df_price['BB_lower'], mode='lines', name='布林下軌', line=dict(width=1, color='rgba(150, 150, 150, 0.5)', dash='dash'), fill='tonexty', fillcolor='rgba(200, 200, 200, 0.1)'))
        
        fig.update_layout(xaxis_rangeslider_visible=False, height=450, template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

        # ==========================================
        # 📉 2. 繪製副指標 (RSI & MACD)
        # ==========================================
        col_rsi, col_macd = st.columns(2)
        with col_rsi:
            st.write("**RSI 相對強弱指標 (14日)**")
            fig_rsi = gr.Figure()
            fig_rsi.add_trace(gr.Scatter(x=df_price.index, y=df_price['RSI'], mode='lines', name='RSI', line=dict(color='purple')))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="超買 (70)")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="超賣 (30)")
            fig_rsi.update_layout(height=200, template="plotly_white", margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_rsi, use_container_width=True)

        with col_macd:
            st.write("**MACD 動能指標**")
            fig_macd = gr.Figure()
            colors_macd = ['red' if val > 0 else 'green' for val in df_price['MACD_diff']]
            fig_macd.add_trace(gr.Bar(x=df_price.index, y=df_price['MACD_diff'], name='Histogram', marker_color=colors_macd))
            fig_macd.add_trace(gr.Scatter(x=df_price.index, y=df_price['MACD'], mode='lines', name='MACD', line=dict(color='blue')))
            fig_macd.add_trace(gr.Scatter(x=df_price.index, y=df_price['MACD_signal'], mode='lines', name='Signal', line=dict(color='orange')))
            fig_macd.update_layout(height=200, template="plotly_white", margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_macd, use_container_width=True)

        st.markdown("---")
        
        # ==========================================
        # 👥 3. 每日三大法人買賣超
        # ==========================================
        st.subheader("👥 每日三大法人買賣超明細（張）")
        if not df_inst.empty:
            df_inst['buy_net_g'] = df_inst['buy'] - df_inst['sell']
            pivot_df = df_inst.pivot(index='date', columns='name', values='buy_net_g').fillna(0)
            pivot_df = pivot_df / 1000
            
            pivot_df['自營商'] = pivot_df.get('自營商買賣超股數(自行買賣)', 0) + pivot_df.get('自營商買賣超股數(避險)', 0) + pivot_df.get('自營商買賣超股數', 0)
            pivot_df['外資'] = pivot_df.get('外陸資買賣超股數', 0)
            pivot_df['投信'] = pivot_df.get('投信買賣超股數', 0)

            summary_inst = pivot_df[['外資', '投信', '自營商']]
            summary_inst.index = pd.to_datetime(summary_inst.index)
            plot_inst = summary_inst.tail(30)
            
            fig_inst = gr.Figure()
            inst_colors = {'外資': 'red', '投信': '#ff9900', '自營商': 'blue'}
            for col in ['外資', '投信', '自營商']:
                fig_inst.add_trace(gr.Bar(x=plot_inst.index, y=plot_inst[col], name=col, marker_color=inst_colors[col]))
            
            fig_inst.update_layout(barmode='group', height=300, template="plotly_white", yaxis_title="買賣超（張）", margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_inst, use_container_width=True)
        else:
            st.warning("暫無該股票的法人買賣超資料（或今日資料尚未更新）。")

else:
    st.warning("請在側邊欄輸入至少一檔股票代號。")
