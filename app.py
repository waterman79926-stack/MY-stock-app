import streamlit as st
import pandas as pd
import plotly.graph_objects as gr
from FinMind.data import DataLoader
from datetime import datetime, timedelta

# 網頁基本設定
st.set_page_config(page_title="我的專屬持股即時監控面板", layout="wide")
st.title("📈 我的專屬持股即時監控面板")

# 初始化 FinMind 資料讀取器
api = DataLoader()

# --- 側邊欄：設定你的持股清單與參數 ---
st.sidebar.header("📌 持股設定與參數")

my_stocks = st.sidebar.text_input(
    "輸入自選股代號（用逗號分隔）", 
    value="2330, 0050, 2454, 2317, 00878"
)
stock_list = [s.strip() for s in my_stocks.split(",") if s.strip()]

# 選擇技術指標參數
st.sidebar.subheader("📊 均線參數設定")
ma_fast = st.sidebar.number_input("快均線 (MA)", min_value=5, max_value=60, value=5)
ma_slow = st.sidebar.number_input("慢均線 (MA)", min_value=10, max_value=240, value=20)

# 計算日期範圍（取最近 180 天的數據）
end_date = datetime.today().strftime('%Y-%m-%d')
start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')

# --- 主畫面 ---
if stock_list:
    selected_stock = st.selectbox("選擇要檢視的股票", stock_list)
    st.subheader(f"🔍 {selected_stock} 詳細盤態分析")
    
    @st.cache_data(ttl=300) 
    def get_stock_data(stock_id, start, end):
        df_price = api.taiwan_stock_daily(stock_id=stock_id, start_date=start, end_date=end)
        df_institutional = api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start, end_date=end)
        return df_price, df_institutional

    try:
        df, df_inst = get_stock_data(selected_stock, start_date, end_date)
        
        if df.empty:
            st.error("找不到該股票資料，或 API 暫時無回應。")
        else:
            # ==========================================
            # 🛡️ 核心防呆與資料清洗 (解決價格錯誤的元兇)
            # ==========================================
            # 1. 確保抓到的資料真的是我們選的股票（防止 FinMind 快取錯亂）
            if 'stock_id' in df.columns:
                df = df[df['stock_id'] == selected_stock]
                
            # 2. 轉換欄位名稱
            df = df.rename(columns={'open': 'Open', 'max': 'High', 'min': 'Low', 'close': 'Close', 'Trading_Volume': 'Volume', 'date': 'Date'})
            
            # 3. 強制按日期排序，防止最後一筆抓到舊資料
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
            df.set_index('Date', inplace=True)
            
            # 4. 剃除股價為 0 的異常資料
            df = df[df['Close'] > 0]

            # ==========================================
            # 📊 重點數據顯示
            # ==========================================
            current_price = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close) * 100 if prev_close != 0 else 0
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("最新收盤價", f"${current_price:.2f}", f"{price_change:+.2f} ({price_change_pct:+.2f}%)")
            col2.metric("今日最高", f"${df['High'].iloc[-1]:.2f}")
            col3.metric("今日最低", f"${df['Low'].iloc[-1]:.2f}")
            col4.metric("成交張數", f"{int(df['Volume'].iloc[-1] / 1000):,} 張")
            
            st.markdown("---")

            # ==========================================
            # 🧮 計算豐富的技術指標 (原生 Pandas 計算)
            # ==========================================
            # 均線
            df['MA_fast'] = df['Close'].rolling(window=ma_fast).mean()
            df['MA_slow'] = df['Close'].rolling(window=ma_slow).mean()
            
            # 布林通道 (Bollinger Bands, 20MA ± 2STD)
            df['STD20'] = df['Close'].rolling(window=20).std()
            df['BB_upper'] = df['MA_slow'] + (df['STD20'] * 2)
            df['BB_lower'] = df['MA_slow'] - (df['STD20'] * 2)

            # RSI (14日)
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))

            # MACD (12, 26, 9)
            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['MACD_diff'] = df['MACD'] - df['MACD_signal']

            # ==========================================
            # 📈 1. 繪製主 K 線圖 + 均線 + 布林通道
            # ==========================================
            st.subheader("📈 主圖：互動 K 線圖與布林通道")
            fig = gr.Figure()
            
            # K線
            fig.add_trace(gr.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name='K線',
                increasing=dict(line=dict(color='#ff3333'), fillcolor='#ff3333'), # 台股紅漲
                decreasing=dict(line=dict(color='#00b33c'), fillcolor='#00b33c')  # 台股綠跌
            ))
            # 均線
            fig.add_trace(gr.Scatter(x=df.index, y=df['MA_fast'], mode='lines', name=f'{ma_fast}MA', line=dict(width=1.5, color='orange')))
            fig.add_trace(gr.Scatter(x=df.index, y=df['MA_slow'], mode='lines', name=f'{ma_slow}MA', line=dict(width=1.5, color='blue')))
            # 布林通道
            fig.add_trace(gr.Scatter(x=df.index, y=df['BB_upper'], mode='lines', name='布林上軌', line=dict(width=1, color='rgba(150, 150, 150, 0.5)', dash='dash')))
            fig.add_trace(gr.Scatter(x=df.index, y=df['BB_lower'], mode='lines', name='布林下軌', line=dict(width=1, color='rgba(150, 150, 150, 0.5)', dash='dash'), fill='tonexty', fillcolor='rgba(200, 200, 200, 0.1)'))
            
            fig.update_layout(xaxis_rangeslider_visible=False, height=500, template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)

            # ==========================================
            # 📉 2. 繪製副指標 (RSI & MACD)
            # ==========================================
            col_rsi, col_macd = st.columns(2)
            
            with col_rsi:
                st.write("**RSI 相對強弱指標 (14日)**")
                fig_rsi = gr.Figure()
                fig_rsi.add_trace(gr.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI', line=dict(color='purple')))
                fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="超買 (70)")
                fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="超賣 (30)")
                fig_rsi.update_layout(height=250, template="plotly_white", margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_rsi, use_container_width=True)

            with col_macd:
                st.write("**MACD 動能指標**")
                fig_macd = gr.Figure()
                # 判斷 MACD 柱狀圖顏色
                colors_macd = ['red' if val > 0 else 'green' for val in df['MACD_diff']]
                fig_macd.add_trace(gr.Bar(x=df.index, y=df['MACD_diff'], name='Histogram', marker_color=colors_macd))
                fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD', line=dict(color='blue')))
                fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD_signal'], mode='lines', name='Signal', line=dict(color='orange')))
                fig_macd.update_layout(height=250, template="plotly_white", margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_macd, use_container_width=True)

            st.markdown("---")
            
            # ==========================================
            # 👥 3. 每日三大法人買賣超
            # ==========================================
            st.subheader("👥 每日三大法人買賣超明細（張）")
            if not df_inst.empty:
                df_inst['buy_net_g'] = df_inst['buy'] - df_inst['sell']
                pivot_df = df_inst.pivot(index='date', columns='name', values='buy_net_g').fillna(0)
                pivot_df = pivot_df / 1000  # 轉為張數
                
                # 嚴謹分類
                pivot_df['自營商'] = pivot_df.get('自營商買賣超股數(自行買賣)', 0) + pivot_df.get('自營商買賣超股數(避險)', 0) + pivot_df.get('自營商買賣超股數', 0)
                pivot_df['外資'] = pivot_df.get('外陸資買賣超股數', 0)
                pivot_df['投信'] = pivot_df.get('投信買賣超股數', 0)

                summary_inst = pivot_df[['外資', '投信', '自營商']]
                summary_inst.index = pd.to_datetime(summary_inst.index)
                plot_inst = summary_inst.tail(30) # 取近 30 日畫圖
                
                fig_inst = gr.Figure()
                inst_colors = {'外資': 'red', '投信': '#ff9900', '自營商': 'blue'}
                for col in ['外資', '投信', '自營商']:
                    fig_inst.add_trace(gr.Bar(x=plot_inst.index, y=plot_inst[col], name=col, marker_color=inst_colors[col]))
                
                fig_inst.update_layout(barmode='group', height=350, template="plotly_white", yaxis_title="買賣超（張）", margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_inst, use_container_width=True)
            else:
                st.warning("暫無該股票的法人買賣超資料。")

            # ==========================================
            # 📋 4. 近 5 日詳細數據表格
            # ==========================================
            st.markdown("---")
            st.write("📋 **近 5 日詳細價量數據**")
            # 準備乾淨的表格供檢視
            df_table = df[['Open', 'High', 'Low', 'Close', 'Volume']].tail(5).copy()
            df_table['Volume'] = (df_table['Volume'] / 1000).astype(int).astype(str) + " 張"
            df_table = df_table.rename(columns={'Open': '開盤', 'High': '最高', 'Low': '最低', 'Close': '收盤', 'Volume': '成交量'})
            st.dataframe(df_table.sort_index(ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"系統處理資料時發生錯誤: {e}")
else:
    st.warning("請在側邊欄輸入至少一檔股票代號。")
