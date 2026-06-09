import streamlit as st
import pandas as pd
import plotly.graph_objects as gr
import yfinance as yf
from FinMind.data import DataLoader
from datetime import datetime, timedelta

# 網頁基本設定
st.set_page_config(page_title="我的專屬持股即時監控面板", layout="wide")
st.title("📈 我的專屬持股即時監控面板")

api = DataLoader()

# --- 取得台股代號與中文名稱對照表 ---
@st.cache_data(ttl=86400) 
def get_stock_names():
    try:
        df_info = api.taiwan_stock_info()
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

# --- 🤖 智能語意分析函數 ---
def generate_ai_analysis(df, df_inst, stock_name, ma_fast_val, ma_slow_val):
    if len(df) < 2:
        return "資料不足，無法產生分析。"
    
    # 抓取最新與前一日數據
    last_price = df['Close'].iloc[-1]
    prev_price = df['Close'].iloc[-2]
    change_pct = ((last_price - prev_price) / prev_price) * 100
    
    ma_f = df['MA_fast'].iloc[-1]
    ma_s = df['MA_slow'].iloc[-1]
    rsi = df['RSI'].iloc[-1]
    macd_diff = df['MACD_diff'].iloc[-1]
    
    # 撰寫趨勢
    trend_text = "偏多 📈" if last_price > ma_f and last_price > ma_s else ("偏空 📉" if last_price < ma_f and last_price < ma_s else "震盪整理 ➖")
    
    # 撰寫動能
    if rsi >= 70: rsi_text = "進入超買區，需留意回檔風險。"
    elif rsi <= 30: rsi_text = "進入超賣區，隨時有機會反彈。"
    else: rsi_text = "處於中性區間。"
    
    macd_text = "紅柱擴大，多方動能轉強。" if macd_diff > 0 else "綠柱擴大，空方動能轉強。"
    
    # 撰寫籌碼
    inst_text = "今日法人籌碼資料尚未更新。"
    if not df_inst.empty and df.index[-1].strftime('%Y-%m-%d') in df_inst.index:
        today_inst = df_inst.loc[df.index[-1].strftime('%Y-%m-%d')]
        f_buy = today_inst.get('外資', 0)
        t_buy = today_inst.get('投信', 0)
        d_buy = today_inst.get('自營商', 0)
        total_buy = f_buy + t_buy + d_buy
        
        inst_dir = "偏多 (買超)" if total_buy > 0 else "偏空 (賣超)"
        inst_text = f"三大法人合計 **{inst_dir} {abs(int(total_buy)):,} 張** (外資: {int(f_buy):+,}張 / 投信: {int(t_buy):+,}張 / 自營: {int(d_buy):+,}張)。"

    # 組裝報告
    report = f"""
    **【股價表現】** 今日收盤價為 **${last_price:.2f}**，較前一日 **{change_pct:+.2f}%**。
    **【技術趨勢】** 目前股價位於 {ma_fast_val}日線 (${ma_f:.2f}) 與 {ma_slow_val}日線 (${ma_s:.2f}) 比較基準，短期整體趨勢 **{trend_text}**。
    **【指標動能】** RSI({rsi:.1f}) {rsi_text} MACD {macd_text}
    **【籌碼動向】** {inst_text}
    """
    return report

# --- 主畫面 ---
if stock_list:
    selected_stock = st.selectbox("選擇要檢視的股票", stock_list)
    
    stock_chinese_name = name_dict.get(selected_stock, "")
    display_title = f"{selected_stock} {stock_chinese_name}" if stock_chinese_name else selected_stock
    
    st.subheader(f"🔍 {display_title} 詳細盤態分析")
    
    @st.cache_data(ttl=300) 
    def get_price_data(stock_id):
        ticker = yf.Ticker(f"{stock_id}.TW")
        df = ticker.history(period="6mo")
        if df.empty:
            ticker = yf.Ticker(f"{stock_id}.TWO")
            df = ticker.history(period="6mo")
        if not df.empty:
            df.index = df.index.tz_localize(None) 
        return df

    @st.cache_data(ttl=300)
    def get_inst_data(stock_id, start, end):
        try:
            return api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start, end_date=end)
        except:
            return pd.DataFrame()

    with st.spinner("資料讀取中..."):
        df_price = get_price_data(selected_stock)
        df_raw_inst = get_inst_data(selected_stock, start_date, end_date)

    if df_price.empty:
        st.error("找不到該股票的歷史價格，請確認代號是否正確。")
    else:
        # ==========================================
        # 🛡️ 籌碼資料：終極安全解析處理
        # ==========================================
        df_inst_clean = pd.DataFrame()
        if not df_raw_inst.empty and 'name' in df_raw_inst.columns and 'buy' in df_raw_inst.columns and 'sell' in df_raw_inst.columns:
            # 建立正規化分類函數
            def categorize_inst(name_str):
                name_str = str(name_str)
                if '外' in name_str or '陸' in name_str: return '外資'
                if '投信' in name_str: return '投信'
                if '自營' in name_str: return '自營商'
                return '其他'
            
            df_raw_inst['法人類別'] = df_raw_inst['name'].apply(categorize_inst)
            df_raw_inst['淨買賣超'] = (df_raw_inst['buy'] - df_raw_inst['sell']) / 1000 # 轉張數
            
            # 樞紐分析：按日期與三大法人彙整
            df_inst_clean = df_raw_inst.pivot_table(index='date', columns='法人類別', values='淨買賣超', aggfunc='sum').fillna(0)
            df_inst_clean.index = pd.to_datetime(df_inst_clean.index)
            
            # 確保欄位存在
            for col in ['外資', '投信', '自營商']:
                if col not in df_inst_clean.columns:
                    df_inst_clean[col] = 0

        # ==========================================
        # 🧮 計算技術指標
        # ==========================================
        df_price['MA_fast'] = df_price['Close'].rolling(window=ma_fast).mean()
        df_price['MA_slow'] = df_price['Close'].rolling(window=ma_slow).mean()
        
        delta = df_price['Close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df_price['RSI'] = 100 - (100 / (1 + rs))

        exp1 = df_price['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df_price['Close'].ewm(span=26, adjust=False).mean()
        df_price['MACD'] = exp1 - exp2
        df_price['MACD_signal'] = df_price['MACD'].ewm(span=9, adjust=False).mean()
        df_price['MACD_diff'] = df_price['MACD'] - df_price['MACD_signal']

        # ==========================================
        # 🤖 智能盤後分析區塊 (新增功能)
        # ==========================================
        st.info(f"**🤖 系統智能盤後解析 ({display_title})**\n" + generate_ai_analysis(df_price, df_inst_clean, selected_stock, ma_fast, ma_slow))

        # ==========================================
        # 📊 價格與 K 線圖
        # ==========================================
        st.subheader("📈 主圖：互動 K 線圖與均線")
        fig = gr.Figure()
        fig.add_trace(gr.Candlestick(
            x=df_price.index, open=df_price['Open'], high=df_price['High'], low=df_price['Low'], close=df_price['Close'],
            name='K線', increasing=dict(line=dict(color='#ff3333'), fillcolor='#ff3333'), decreasing=dict(line=dict(color='#00b33c'), fillcolor='#00b33c')
        ))
        fig.add_trace(gr.Scatter(x=df_price.index, y=df_price['MA_fast'], mode='lines', name=f'{ma_fast}MA', line=dict(width=1.5, color='orange')))
        fig.add_trace(gr.Scatter(x=df_price.index, y=df_price['MA_slow'], mode='lines', name=f'{ma_slow}MA', line=dict(width=1.5, color='blue')))
        fig.update_layout(xaxis_rangeslider_visible=False, height=450, template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

        # ==========================================
        # 👥 三大法人買賣超長條圖
        # ==========================================
        st.subheader("👥 每日三大法人買賣超明細（張）")
        
        # 萬一真的沒資料，提供除錯按鈕讓你看原始資料長怎樣
        with st.expander("🛠️ 查看 FinMind 原始籌碼數據 (除錯用)"):
            if not df_raw_inst.empty:
                st.dataframe(df_raw_inst.tail(15))
            else:
                st.write("API 完全沒有回傳這檔股票的籌碼資料！")

        if not df_inst_clean.empty:
            plot_inst = df_inst_clean.tail(30)
            fig_inst = gr.Figure()
            inst_colors = {'外資': 'red', '投信': '#ff9900', '自營商': 'blue'}
            for col in ['外資', '投信', '自營商']:
                fig_inst.add_trace(gr.Bar(x=plot_inst.index, y=plot_inst[col], name=col, marker_color=inst_colors[col]))
            
            fig_inst.update_layout(barmode='group', height=300, template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_inst, use_container_width=True)
        else:
            st.warning("⚠️ 籌碼資料處理失敗，或今日資料尚未更新。請點擊上方「查看原始籌碼數據」檢查 API 是否有回傳值。")

else:
    st.warning("請在側邊欄輸入至少一檔股票代號。")
