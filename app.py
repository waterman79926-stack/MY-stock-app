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

# --- 側邊欄：設定你的持股清單 ---
st.sidebar.header("📌 持股設定與參數")

my_stocks = st.sidebar.text_input(
    "輸入自選股代號（用逗號分隔）", 
    value="2330, 00923, 0050, 00713, 00878"
)
stock_list = [s.strip() for s in my_stocks.split(",") if s.strip()]

# 選擇技術指標參數
st.sidebar.subheader("📊 技術指標設定")
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
            st.error("找不到該股票資料。")
        else:
            # ⚠️ 這裡是最關鍵的修正：正確對應 FinMind 的 max, min 與 Trading_Volume 欄位
            df = df.rename(columns={
                'open': 'Open', 
                'max': 'High', 
                'min': 'Low', 
                'close': 'Close', 
                'Trading_Volume': 'Volume', 
                'date': 'Date'
            })
            df.set_index('Date', inplace=True)
            
            # 1. 顯示重點數據
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
            
            # 2. 計算技術指標
            df['MA_fast'] = df['Close'].rolling(window=ma_fast).mean()
            df['MA_slow'] = df['Close'].rolling(window=ma_slow).mean()
            
            # 3. 繪製 K 線圖
            st.subheader("📈 互動式技術線圖（含移動平均線）")
            fig = gr.Figure()
            
            fig.add_trace(gr.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name='K線', 
                increasing_line_color='red', increasing_fill_color='red',
                decreasing_line_color='green', decreasing_fill_color='green'
            ))
            fig.add_trace(gr.Scatter(x=df.index, y=df['MA_fast'], mode='lines', name=f'{ma_fast}MA', line=dict(width=1.5)))
            fig.add_trace(gr.Scatter(x=df.index, y=df['MA_slow'], mode='lines', name=f'{ma_slow}MA', line=dict(width=1.5)))
            
            fig.update_layout(xaxis_rangeslider_visible=False, height=450, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            
            # 4. 法人買賣超
            st.subheader("👥 每日三大法人買賣超明細（張）")
            if not df_inst.empty:
                df_inst['buy_net_g'] = df_inst['buy'] - df_inst['sell']
                pivot_df = df_inst.pivot(index='date', columns='name', values='buy_net_g').fillna(0)
                pivot_df = pivot_df / 1000  
                
                plot_inst = pivot_df.tail(30)
                
                fig_inst = gr.Figure()
                colors = {'外陸資買賣超股數': 'red', '投信買賣超股數': 'orange', '自營商買賣超股數': 'blue', '自營商買賣超股數(自行買賣)': 'blue'}
                labels = {'外陸資買賣超股數': '外資', '投信買賣超股數': '投信', '自營商買賣超股數': '自營商', '自營商買賣超股數(自行買賣)': '自營商(自行)'}
                
                for col in plot_inst.columns:
                    if col in labels:
                        fig_inst.add_trace(gr.Bar(
                            x=plot_inst.index, y=plot_inst[col], 
                            name=labels[col], marker_color=colors.get(col, 'gray')
                        ))
                
                fig_inst.update_layout(barmode='group', height=350, template="plotly_white", yaxis_title="買賣超（張）")
                st.plotly_chart(fig_inst, use_container_width=True)
                
                st.write("**最新交易日法人進出數據：**")
                latest_date = pivot_df.index[-1]
                cols_data = pivot_df.loc[latest_date]
                c1, c2, c3 = st.columns(3)
                c1.metric("外資買賣超", f"{cols_data.get('外陸資買賣超股數', 0):+,.0f} 張")
                c2.metric("投信買賣超", f"{cols_data.get('投信買賣超股數', 0):+,.0f} 張")
                c3.metric("自營商買賣超", f"{cols_data.get('自營商買賣超股數', 0) + cols_data.get('自營商買賣超股數(自行買賣)', 0):+,.0f} 張")
            else:
                st.warning("暫無該股票的法人買賣超資料。")

    except Exception as e:
        st.error(f"讀取資料時發生錯誤: {e}")
