import streamlit as st
import pandas as pd
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
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
    value="2330, 00923, 0050, 00713, 00878"
)
# 整理輸入的代號清單，移除空白並過濾空值
stock_list = [s.strip() for s in my_stocks.split(",") if s.strip()]

# 選擇技術指標參數
st.sidebar.subheader("📊 技術指標設定")
ma_fast = st.sidebar.number_input("快均線 (MA)", min_value=5, max_value=60, value=5)
ma_slow = st.sidebar.number_input("慢均線 (MA)", min_value=10, max_value=240, value=20)

# 計算日期範圍（預設取最近 180 天的數據）
end_date = datetime.today().strftime('%Y-%m-%d')
start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')

# --- 主畫面 ---
if stock_list:
    # 選擇目前要檢視的股票
    selected_stock = st.selectbox("選擇要檢視的股票", stock_list)
    st.subheader(f"🔍 {selected_stock} 詳細盤態分析")
    
    # 讀取股價資料與法人資料（快取以減少 API 呼叫）
    @st.cache_data(ttl=300) 
    def get_stock_data(stock_id, start, end):
        # 抓取日 K 線資料
        df_price = api.taiwan_stock_daily(stock_id=stock_id, start_date=start, end_date=end)
        # 抓取三大法人買賣超資料
        df_institutional = api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start, end_date=end)
        return df_price, df_institutional

    try:
        df, df_inst = get_stock_data(selected_stock, start_date, end_date)
        
        if df.empty:
            st.error("找不到該股票資料。")
        else:
            # 整理股價資料欄位
            df = df.rename(columns={
                'open': 'Open', 
                'max': 'High', 
                'min': 'Low', 
                'close': 'Close', 
                'Trading_Volume': 'Volume', 
                'date': 'Date'
            })
            df.set_index('Date', inplace=True)
            
            # 1. 顯示重點數據 (最新一交易日)
            current_price = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close) * 100 if prev_close != 0 else 0
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("最新收盤價", f"${current_price:.2f}", f"{price_change:+.2f} ({price_change_pct:+.2f}%)")
            col2.metric("今日最高", f"${df['High'].iloc[-1]:.2f}")
            col3.metric("今日最低", f"${df['Low'].iloc[-1]:.2f}")
            # 成交量 FinMind 為股數，除以 1000 轉換為張數
            col4.metric("成交張數", f"{int(df['Volume'].iloc[-1] / 1000):,} 張")
            
            st.markdown("---")
            
            # 2. 計算技術指標
            df['MA_fast'] = df['Close'].rolling(window=ma_fast).mean()
            df['MA_slow'] = df['Close'].rolling(window=ma_slow).mean()
            
            # 3. 繪製 K 線圖（此處已修正 `increasing_fill_color` 的錯誤）
            st.subheader("📈 互動式技術線圖（含移動平均線）")
            fig = gr.Figure()
            
            # K線 (台灣習慣：紅漲綠跌)
            # ⚠️ 這裡是最關鍵的修正：正確設定 `increasing` 與 `decreasing` 的 fillcolor 屬性
            fig.add_trace(gr.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name='K線',
                increasing=dict(line=dict(color='red'), fillcolor='red'),
                decreasing=dict(line=dict(color='green'), fillcolor='green')
            ))
            # 均線
            fig.add_trace(gr.Scatter(x=df.index, y=df['MA_fast'], mode='lines', name=f'{ma_fast}MA', line=dict(width=1.5, color='orange')))
            fig.add_trace(gr.Scatter(x=df.index, y=df['MA_slow'], mode='lines', name=f'{ma_slow}MA', line=dict(width=1.5, color='blue')))
            
            fig.update_layout(xaxis_rangeslider_visible=False, height=450, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            
            # 4. 每日三大法人買賣超圖表
            st.subheader("👥 每日三大法人買賣超明細（張）")
            if not df_inst.empty:
                # 計算淨買賣（買 - 賣）
                df_inst['buy_net_g'] = df_inst['buy'] - df_inst['sell']
                
                # 嚴謹處理不同類型的自營商與外資欄位
                # 先進行樞紐分析
                pivot_df = df_inst.pivot(index='date', columns='name', values='buy_net_g').fillna(0)
                
                # 成股數轉張數
                pivot_df = pivot_df / 1000  
                
                # 嚴謹地將相關類別加總（加總所有自營商類別）
                # 注意：FinMind 回傳的名稱可能會依資料源略有不同，這裡嘗試處理可能的變體
                if '自營商買賣超股數(自行買賣)' in pivot_df.columns and '自營商買賣超股數(避險)' in pivot_df.columns:
                    pivot_df['自營商'] = pivot_df['自營商買賣超股數(自行買賣)'] + pivot_df['自營商買賣超股數(避險)']
                elif '自營商買賣超股數(自行買賣)' in pivot_df.columns:
                    pivot_df['自營商'] = pivot_df['自營商買賣超股數(自行買賣)']
                elif '自營商買賣超股數' in pivot_df.columns:
                    pivot_df['自營商'] = pivot_df['自營商買賣超股數']
                else:
                    pivot_df['自營商'] = 0

                # 處理外資
                if '外陸資買賣超股數' in pivot_df.columns:
                    pivot_df['外資'] = pivot_df['外陸資買賣超股數']
                else:
                    pivot_df['外資'] = 0

                # 處理投信
                if '投信買賣超股數' in pivot_df.columns:
                    pivot_df['投信'] = pivot_df['投信買賣超股數']
                else:
                    pivot_df['投信'] = 0

                # 只保留加總後的重點欄位並重新整理索引
                summary_inst = pivot_df[['外資', '投信', '自營商']]
                summary_inst.index = pd.to_datetime(summary_inst.index)
                
                # 只取最近 30 個交易日展示
                plot_inst = summary_inst.tail(30)
                
                # 繪製柱狀圖
                fig_inst = gr.Figure()
                inst_colors = {'外資': 'red', '投信': 'orange', '自營商': 'blue'}
                
                for col in ['外資', '投信', '自營商']:
                    fig_inst.add_trace(gr.Bar(
                        x=plot_inst.index, y=plot_inst[col], 
                        name=col, marker_color=inst_colors[col]
                    ))
                
                fig_inst.update_layout(barmode='group', height=350, template="plotly_white", yaxis_title="買賣超（張）")
                st.plotly_chart(fig_inst, use_container_width=True)
                
                # 顯示最新一日的法人具體數字
                st.write("**最新交易日法人進出數據（張）：**")
                latest_inst_date = summary_inst.index[-1]
                cols_inst_data = summary_inst.loc[latest_inst_date]
                c1, c2, c3 = st.columns(3)
                c1.metric("外資買賣超", f"{cols_inst_data['外資']:+,.0f} 張")
                c2.metric("投信買賣超", f"{cols_inst_data['投信']:+,.0f} 張")
                c3.metric("自營商買賣超", f"{cols_inst_data['自營商']:+,.0f} 張")
            else:
                st.warning("暫無該股票的法人買賣超資料。")

    except Exception as e:
        st.error(f"讀取或處理資料時發生錯誤: {e}")
else:
    st.warning("請在側邊欄輸入至少一檔股票代號。")
