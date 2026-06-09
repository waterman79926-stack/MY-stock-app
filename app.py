import streamlit as st
import pandas as pd
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
import yfinance as yf
from FinMind.data import DataLoader
from datetime import datetime, timedelta

# 網頁基本設定
st.set_page_config(page_title="我的專屬持股即時監控面板", layout="wide")
st.title("📈 我的專屬持股即時監控面板")

api = DataLoader()

# --- 取得台股代號與中文名稱 ---
@st.cache_data(ttl=86400) 
def get_stock_names():
    try:
        df_info = api.taiwan_stock_info()
        return dict(zip(df_info['stock_id'], df_info['stock_name']))
    except:
        return {}

name_dict = get_stock_names()

# --- 側邊欄設定 ---
st.sidebar.header("📌 持股設定與參數")
my_stocks = st.sidebar.text_input("輸入自選股代號（用逗號分隔）", value="2330, 0050, 2454, 2317, 00878")
stock_list = [s.strip() for s in my_stocks.split(",") if s.strip()]

st.sidebar.subheader("📊 均線參數")
ma_fast = st.sidebar.number_input("快均線 (MA)", min_value=5, max_value=60, value=5)
ma_slow = st.sidebar.number_input("慢均線 (MA)", min_value=10, max_value=240, value=20)

end_date = datetime.today().strftime('%Y-%m-%d')
start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')

# --- 🤖 專業投顧 AI 分析引擎 ---
def generate_pro_analysis(df, df_inst, stock_name, f_ma, s_ma):
    if len(df) < 20: return "資料不足，無法進行深度解析。"
    
    close = df['Close'].iloc[-1]
    ma_f_val = df['MA_fast'].iloc[-1]
    ma_s_val = df['MA_slow'].iloc[-1]
    rsi = df['RSI'].iloc[-1]
    macd_hist = df['MACD_diff'].iloc[-1]
    macd_hist_prev = df['MACD_diff'].iloc[-2]
    
    # 趨勢判定
    if close > ma_f_val > ma_s_val:
        trend = "均線呈現標準『多頭排列』，多方控盤格局明確，下方支撐強勁。"
    elif close < ma_f_val < ma_s_val:
        trend = "均線呈現『空頭排列』，上檔反壓沉重，目前處於弱勢探底階段，不宜貿然摸底。"
    elif close > ma_s_val and close < ma_f_val:
        trend = "股價跌破短均線但仍守住長均線，處於『高檔震盪整理』，需觀察是否能快速站回短線支撐。"
    else:
        trend = "均線糾結，目前處於『無方向性的盤整區間』，正在醞釀下一波表態。"

    # 動能判定
    if rsi >= 75: momentum = f"RSI 來到 {rsi:.1f} 的高檔超買區，需提防高檔鈍化後的獲利了結賣壓。"
    elif rsi <= 25: momentum = f"RSI 降至 {rsi:.1f} 嚴重超賣，短線醞釀技術性反彈契機。"
    else:
        if macd_hist > 0 and macd_hist > macd_hist_prev:
            momentum = "MACD 紅柱持續放大，多方攻擊動能正在增溫。"
        elif macd_hist < 0 and macd_hist < macd_hist_prev:
            momentum = "MACD 綠柱擴散，空方動能增強，需提高風險意識。"
        else:
            momentum = "MACD 動能溫和，無明顯表態。"

    # 籌碼判定
    inst_comment = "今日法人籌碼尚未出爐，需留意尾盤主力動向。"
    if not df_inst.empty and df.index[-1].strftime('%Y-%m-%d') in df_inst.index:
        today_inst = df_inst.loc[df.index[-1].strftime('%Y-%m-%d')]
        f_buy = today_inst.get('外資', 0)
        t_buy = today_inst.get('投信', 0)
        total = f_buy + t_buy + today_inst.get('自營商', 0)
        
        if f_buy > 0 and t_buy > 0:
            inst_comment = f"【土洋對作終結】外資與投信今日『同步買超』共 {int(f_buy+t_buy):,} 張，籌碼集中度極高，對後市具備推升力道。"
        elif f_buy < 0 and t_buy < 0:
            inst_comment = f"【土洋雙殺】外資與投信今日『同步倒貨』，須警戒籌碼鬆動引發的多殺多效應。"
        elif total > 0:
            inst_comment = f"三大法人合計偏多操作，買超 {int(total):,} 張，主要由{'外資' if f_buy > t_buy else '投信'}主導進場。"
        else:
            inst_comment = f"三大法人偏空操作，賣超 {abs(int(total)):,} 張，顯示大戶目前心態偏向保守提現。"

    report = f"""
    👨‍🏫 **【大盤與個股綜整評估】** 從技術面來看，{trend} {momentum} 
    在籌碼面部分，{inst_comment}
    👉 **操作建議**：若為長線投資者，可觀察 {s_ma}MA (${ma_s_val:.2f}) 的防守力道；短線當沖或波段客，則需留意量能是否能持續放大來突破前波高點。
    """
    return report

# --- 主畫面 ---
if stock_list:
    selected_stock = st.selectbox("選擇要檢視的股票", stock_list)
    
    stock_chinese_name = name_dict.get(selected_stock, "")
    display_title = f"{selected_stock} {stock_chinese_name}" if stock_chinese_name else selected_stock
    
    st.subheader(f"🔍 {display_title} 全方位盤態分析")
    
    # 抓取 5 年資料以計算長線報酬
    # 修正重點：只回傳純資料 (df, divs)，不回傳 ticker 物件，避開 Serialization Error
    @st.cache_data(ttl=300) 
    def get_price_data(stock_id):
        ticker = yf.Ticker(f"{stock_id}.TW")
        df = ticker.history(period="5y")
        divs = pd.Series(dtype='float64')
        if df.empty:
            ticker = yf.Ticker(f"{stock_id}.TWO")
            df = ticker.history(period="5y")
        if not df.empty:
            df.index = df.index.tz_localize(None) 
            try:
                divs = ticker.dividends
            except:
                pass
        return df, divs

    @st.cache_data(ttl=300)
    def get_inst_data(stock_id, start, end):
        try:
            return api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start, end_date=end)
        except:
            return pd.DataFrame()

    with st.spinner("深度資料運算中..."):
        df_price, divs_data = get_price_data(selected_stock)
        df_raw_inst = get_inst_data(selected_stock, start_date, end_date)

    if df_price.empty:
        st.error("找不到該股票的歷史價格，請確認代號是否正確。")
    else:
        # ==========================================
        # 🛡️ 籌碼資料：中英文雙重防護解析
        # ==========================================
        df_inst_clean = pd.DataFrame()
        if not df_raw_inst.empty and 'name' in df_raw_inst.columns:
            def categorize_inst(name_str):
                ns = str(name_str).lower()
                if 'foreign' in ns or '外' in ns or '陸' in ns: return '外資'
                if 'trust' in ns or '投信' in ns: return '投信'
                if 'dealer' in ns or '自營' in ns: return '自營商'
                return '其他'
            
            df_raw_inst['法人類別'] = df_raw_inst['name'].apply(categorize_inst)
            df_raw_inst['淨買賣超'] = (df_raw_inst['buy'] - df_raw_inst['sell']) / 1000
            
            df_inst_clean = df_raw_inst.pivot_table(index='date', columns='法人類別', values='淨買賣超', aggfunc='sum').fillna(0)
            df_inst_clean.index = pd.to_datetime(df_inst_clean.index)
            for col in ['外資', '投信', '自營商']:
                if col not in df_inst_clean.columns: df_inst_clean[col] = 0

        # ==========================================
        # 🧮 績效計算與重點數據
        # ==========================================
        current_price = df_price['Close'].iloc[-1]
        prev_close = df_price['Close'].iloc[-2] if len(df_price) > 1 else current_price
        price_change = current_price - prev_close
        price_change_pct = (price_change / prev_close) * 100 if prev_close != 0 else 0
        
        st.write("### 💵 即時股價與歷史獲利表現")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新收盤價", f"${current_price:.2f}", f"{price_change:+.2f} ({price_change_pct:+.2f}%)")
        c2.metric("今日最高", f"${df_price['High'].iloc[-1]:.2f}")
        c3.metric("今日最低", f"${df_price['Low'].iloc[-1]:.2f}")
        c4.metric("成交張數", f"{int(df_price['Volume'].iloc[-1] / 1000):,} 張")
        
        # 計算歷史報酬率
        returns = {}
        for label, days in [("近一月", 21), ("近三月", 63), ("近半年", 126), ("近一年", 252), ("近五年", 1260)]:
            if len(df_price) > days:
                past_price = df_price['Close'].iloc[-days-1]
                ret = ((current_price - past_price) / past_price) * 100
                returns[label] = f"{ret:+.2f}%"
            else:
                returns[label] = "上市未滿"

        r1, r2, r3, r4, r5 = st.columns(5)
        r1.metric("近一月報酬", returns['近一月'])
        r2.metric("近三月報酬", returns['近三月'])
        r3.metric("近半年報酬", returns['近半年'])
        r4.metric("近一年報酬", returns['近一年'])
        r5.metric("近五年報酬", returns['近五年'])
        
        st.markdown("---")

        # ==========================================
        # 💰 除權息資訊
        # ==========================================
        st.write("### 💰 近期配息資訊")
        if not divs_data.empty:
            recent_divs = divs_data.tail(3).sort_index(ascending=False)
            div_str = " | ".join([f"**{date.strftime('%Y-%m-%d')}** 除息 **${amt:.2f}**" for date, amt in recent_divs.items()])
            st.info(f"📅 最新配息紀錄：{div_str}")
        else:
            st.write("無近期配息紀錄，或此檔股票無配息。")

        st.markdown("---")

        # 計算指標 (切回半年資料畫圖避免太擠)
        df_plot = df_price.tail(150).copy()
        df_plot['MA_fast'] = df_plot['Close'].rolling(window=ma_fast).mean()
        df_plot['MA_slow'] = df_plot['Close'].rolling(window=ma_slow).mean()
        
        delta = df_plot['Close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        df_plot['RSI'] = 100 - (100 / (1 + (gain / loss)))

        exp1 = df_plot['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df_plot['Close'].ewm(span=26, adjust=False).mean()
        df_plot['MACD'] = exp1 - exp2
        df_plot['MACD_signal'] = df_plot['MACD'].ewm(span=9, adjust=False).mean()
        df_plot['MACD_diff'] = df_plot['MACD'] - df_plot['MACD_signal']

        # ==========================================
        # 🤖 智能投顧解析區塊
        # ==========================================
        st.success(generate_pro_analysis(df_plot, df_inst_clean, display_title, ma_fast, ma_slow))

        # ==========================================
        # 📈 1. 繪製主 K 線圖 + 成交量 Bar (Subplots)
        # ==========================================
        st.subheader("📈 主圖：K 線與成交量")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        
        # 上半部：K線與均線
        fig.add_trace(gr.Candlestick(
            x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'],
            name='K線', increasing=dict(line=dict(color='#ff3333'), fillcolor='#ff3333'), decreasing=dict(line=dict(color='#00b33c'), fillcolor='#00b33c')
        ), row=1, col=1)
        fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['MA_fast'], mode='lines', name=f'{ma_fast}MA', line=dict(width=1.5, color='orange')), row=1, col=1)
        fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['MA_slow'], mode='lines', name=f'{ma_slow}MA', line=dict(width=1.5, color='blue')), row=1, col=1)
        
        # 下半部：成交量
        colors_vol = ['#ff3333' if df_plot['Close'].iloc[i] > df_plot['Open'].iloc[i] else '#00b33c' for i in range(len(df_plot))]
        fig.add_trace(gr.Bar(x=df_plot.index, y=df_plot['Volume'], marker_color=colors_vol, name='成交股數'), row=2, col=1)
        
        fig.update_layout(xaxis_rangeslider_visible=False, height=600, template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

        # ==========================================
        # 👥 三大法人買賣超
        # ==========================================
        st.subheader("👥 每日三大法人買賣超明細（張）")
        
        with st.expander("🛠️ 展開查看 FinMind 原始籌碼數據"):
            if not df_raw_inst.empty: st.dataframe(df_raw_inst.tail(15))
            else: st.write("無原始資料")

        if not df_inst_clean.empty:
            plot_inst = df_inst_clean.tail(30)
            fig_inst = gr.Figure()
            inst_colors = {'外資': 'red', '投信': '#ff9900', '自營商': 'blue'}
            for col in ['外資', '投信', '自營商']:
                fig_inst.add_trace(gr.Bar(x=plot_inst.index, y=plot_inst[col], name=col, marker_color=inst_colors[col]))
            
            fig_inst.update_layout(barmode='group', height=350, template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_inst, use_container_width=True)
        else:
            st.warning("⚠️ 籌碼資料處理失敗，或今日資料尚未更新。")

else:
    st.warning("請在側邊欄輸入至少一檔股票代號。")
