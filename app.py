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

# ==========================================
# 📌 側邊欄：一體化選股與快捷按鍵
# ==========================================
if 'selected_stock' not in st.session_state:
    st.session_state.selected_stock = '0050'

st.sidebar.header("📌 持股設定")

# 1. 單一輸入框
user_input = st.sidebar.text_input("輸入股票代號 (按 Enter 確定)", value=st.session_state.selected_stock)
if user_input != st.session_state.selected_stock:
    st.session_state.selected_stock = user_input
    st.rerun()

# 2. 常用股票快捷鍵
st.sidebar.write("⚡ 常用自選股：")
quick_stocks = ["0050", "2330", "2317"]
cols = st.sidebar.columns(3)
for i, stock in enumerate(quick_stocks):
    if cols[i].button(stock):
        st.session_state.selected_stock = stock
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📊 均線參數")
ma_fast = st.sidebar.number_input("快均線 (MA)", min_value=5, max_value=60, value=5)
ma_slow = st.sidebar.number_input("慢均線 (MA)", min_value=10, max_value=240, value=20)

st.sidebar.markdown("---")
st.sidebar.subheader("📅 圖表檢視區間")
timeframe = st.sidebar.radio("選擇互動圖表範圍", ["近一月", "近三月", "近半年", "近一年", "近五年"])

end_date = datetime.today().strftime('%Y-%m-%d')
start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')
selected_stock = st.session_state.selected_stock

# ==========================================
# 🤖 專業投顧 AI 分析引擎 (對齊排版版)
# ==========================================
def generate_pro_analysis(df, df_inst, stock_name, f_ma, s_ma):
    if len(df) < 20: return "資料不足，無法進行深度解析。"
    
    close = df['Close'].iloc[-1]
    ma_f_val = df['MA_fast'].iloc[-1]
    ma_s_val = df['MA_slow'].iloc[-1]
    rsi = df['RSI'].iloc[-1]
    macd_hist = df['MACD_diff'].iloc[-1]
    macd_hist_prev = df['MACD_diff'].iloc[-2]
    
    if close > ma_f_val > ma_s_val:
        trend = "均線呈現漂亮的『多頭排列』，目前多方牢牢掌握控盤權，下方支撐十分強勁。"
    elif close < ma_f_val < ma_s_val:
        trend = "均線已跌至『空頭排列』，上檔累積了不小的套牢反壓，目前還在弱勢探底，絕對不宜貿然進場接刀。"
    elif close > ma_s_val and close < ma_f_val:
        trend = "股價雖跌破短均線，但仍力守長均線生命線，屬於『高檔強勢整理』，後續看能否補量快速站回短均線。"
    else:
        trend = "均線呈現糾結，處於『無方向性的沉悶盤整』，主力似乎還在觀望、醞釀下一波表態方向。"

    if rsi >= 75: momentum = f"而且 RSI 已經飆到 {rsi:.1f} 的過熱超買區，隨時可能會有獲利了結的賣壓湧現。"
    elif rsi <= 25: momentum = f"另外 RSI 降至 {rsi:.1f} 的嚴重超賣區，短線上浮現出跌深反彈的契機。"
    else:
        if macd_hist > 0 and macd_hist > macd_hist_prev: momentum = "MACD 紅柱持續放大，顯示多方攻擊的火種正在逐漸延燒。"
        elif macd_hist < 0 and macd_hist < macd_hist_prev: momentum = "MACD 綠柱擴散，空方下殺動能增強，需提高持股的風險意識。"
        else: momentum = "MACD 動能表現溫吞，缺乏明顯的爆發力道。"

    inst_comment = "今日法人籌碼尚未更新，建議尾盤再做最後確認。"
    if not df_inst.empty and df.index[-1].strftime('%Y-%m-%d') in df_inst.index:
        today_inst = df_inst.loc[df.index[-1].strftime('%Y-%m-%d')]
        f_buy, t_buy, d_buy = today_inst.get('外資', 0), today_inst.get('投信', 0), today_inst.get('自營商', 0)
        total = f_buy + t_buy + d_buy
        
        if f_buy > 0 and t_buy > 0: inst_comment = f"【土洋聯手做多】外資與投信今日『同步買超』共 {int(f_buy+t_buy):,} 張，籌碼高度集中在大戶手上，這對後續股價推升非常有戲。"
        elif f_buy < 0 and t_buy < 0: inst_comment = f"【土洋無情雙殺】外資與投信今日『同步倒貨』，大戶都在跑路，必須嚴防籌碼鬆動引發的連環多殺多。"
        elif total > 0: inst_comment = f"三大法人合計偏多操作，加碼了 {int(total):,} 張，背後主要是{'外資' if f_buy > t_buy else '投信'}在撐盤進場。"
        else: inst_comment = f"三大法人整體偏向提款，賣超 {abs(int(total)):,} 張，顯示法人大戶現階段心態相當保守。"

    if close > ma_s_val: strategy = f"目前大趨勢依舊站在多方，建議可以沿著 {s_ma}日線 (${ma_s_val:.2f}) 偏多操作。只要不跌破，持股續抱讓獲利奔跑；空手者可等量縮回測均線時再找買點，切忌盲目追高。"
    else: strategy = "現在上方重重套牢賣壓，趨勢明顯轉弱。強烈建議多看少做，『現金為王』。若真的手癢想搶反彈，手腳一定要快，並嚴格把今天低點當作停損防守線。"

    # 使用 Markdown 項目符號確保多行文字能完美縮排對齊
    return (
        f"* **💡 盤後重點速覽**：今天 {stock_name} 收在 **${close:.2f}**。就技術線型來看，{trend} {momentum}\n"
        f"* **🕵️‍♂️ 籌碼追蹤**：{inst_comment}\n"
        f"* **🎯 AI 分析師實戰建議**：{strategy}"
    )

# ==========================================
# 📊 抓取資料模組
# ==========================================
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
        try: divs = ticker.dividends
        except: pass
    return df, divs

@st.cache_data(ttl=300)
def get_inst_data(stock_id, start, end):
    try: return api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start, end_date=end)
    except: return pd.DataFrame()

# 精準 Google 即時新聞 (以發布時間排序)
@st.cache_data(ttl=1800)
def get_stock_news(query):
    # 搜尋條件加入 when:7d 確保不會抓到太舊的新聞
    url = f"https://news.google.com/rss/search?q={quote(query)}+when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        news = []
        for item in root.findall('./channel/item'):
            title = item.find('title').text
            link = item.find('link').text
            pub_date_str = item.find('pubDate').text
            # 將 RSS 時間轉為真實 datetime 物件
            pub_date = email.utils.parsedate_to_datetime(pub_date_str)
            news.append({'title': title, 'link': link, 'date': pub_date})
        
        # 依日期由新到舊排序，取前 3 則
        news = sorted(news, key=lambda x: x['date'], reverse=True)[:3]
        for n in news:
            n['date_str'] = n['date'].strftime('%Y-%m-%d %H:%M') # 格式化時間
        return news
    except:
        return []

# ==========================================
# 🚀 主畫面呈現
# ==========================================
if selected_stock:
    stock_chinese_name = name_dict.get(selected_stock, "")
    display_title = f"{selected_stock} {stock_chinese_name}" if stock_chinese_name else selected_stock
    
    st.subheader(f"🔍 {display_title} 全方位盤態分析")
    
    with st.spinner("深度資料運算中..."):
        df_price, divs_data = get_price_data(selected_stock)
        df_raw_inst = get_inst_data(selected_stock, start_date, end_date)

    if df_price.empty:
        st.error("找不到該股票的歷史價格，請確認代號是否正確。")
    else:
        # --- 數據計算區 ---
        df_price['MA_fast'] = df_price['Close'].rolling(window=ma_fast).mean()
        df_price['MA_slow'] = df_price['Close'].rolling(window=ma_slow).mean()
        delta = df_price['Close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        df_price['RSI'] = 100 - (100 / (1 + (gain / loss)))
        exp1 = df_price['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df_price['Close'].ewm(span=26, adjust=False).mean()
        df_price['MACD'] = exp1 - exp2
        df_price['MACD_signal'] = df_price['MACD'].ewm(span=9, adjust=False).mean()
        df_price['MACD_diff'] = df_price['MACD'] - df_price['MACD_signal']

        df_inst_clean = pd.DataFrame()
        if not df_raw_inst.empty and 'name' in df_raw_inst.columns:
            def cat_inst(ns):
                ns = str(ns).lower()
                if 'foreign' in ns or '外' in ns or '陸' in ns: return '外資'
                if 'trust' in ns or '投信' in ns: return '投信'
                if 'dealer' in ns or '自營' in ns: return '自營商'
                return '其他'
            df_raw_inst['法人類別'] = df_raw_inst['name'].apply(cat_inst)
            df_raw_inst['淨買賣超'] = (df_raw_inst['buy'] - df_raw_inst['sell']) / 1000
            df_inst_clean = df_raw_inst.pivot_table(index='date', columns='法人類別', values='淨買賣超', aggfunc='sum').fillna(0)
            df_inst_clean.index = pd.to_datetime(df_inst_clean.index)
            for col in ['外資', '投信', '自營商']:
                if col not in df_inst_clean.columns: df_inst_clean[col] = 0

        # --- 💵 即時股價 (移除報酬率行列) ---
        current_price = df_price['Close'].iloc[-1]
        prev_close = df_price['Close'].iloc[-2] if len(df_price) > 1 else current_price
        price_change = current_price - prev_close
        price_change_pct = (price_change / prev_close) * 100 if prev_close != 0 else 0
        
        st.write("### 💵 即時股價重點")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新收盤價", f"${current_price:.2f}", f"{price_change:+.2f} ({price_change_pct:+.2f}%)")
        c2.metric("今日最高", f"${df_price['High'].iloc[-1]:.2f}")
        c3.metric("今日最低", f"${df_price['Low'].iloc[-1]:.2f}")
        c4.metric("成交張數", f"{int(df_price['Volume'].iloc[-1] / 1000):,} 張")
        
        st.markdown("---")

        # --- 💰 近 5 年配息圖表與殖利率試算 (改用可靠的 yfinance 資料) ---
        st.write("### 💰 歷年配息與殖利率 (以現價試算)")
        if not divs_data.empty:
            divs_df = pd.DataFrame({'date': divs_data.index, 'cash_dividend': divs_data.values})
            divs_df['year'] = pd.to_datetime(divs_df['date']).dt.year
            annual_div = divs_df.groupby('year')['cash_dividend'].sum().reset_index()
            # 排除 0 元與當前年份若尚未配完的極端小值，取最近5年
            annual_div = annual_div[annual_div['cash_dividend'] > 0].tail(5) 
            
            if not annual_div.empty:
                latest_div = annual_div['cash_dividend'].iloc[-1]
                avg_div = annual_div['cash_dividend'].mean()
                
                c_y1, c_y2 = st.columns(2)
                c_y1.metric(f"{annual_div['year'].iloc[-1]}年度 現金股利", f"${latest_div:.2f}", f"當前殖利率估算: {(latest_div/current_price)*100:.2f}%", delta_color="normal")
                c_y2.metric("近五年 平均股利", f"${avg_div:.2f}", f"平均殖利率估算: {(avg_div/current_price)*100:.2f}%", delta_color="normal")
                
                fig_div = gr.Figure(gr.Bar(
                    x=annual_div['year'].astype(str) + "年", y=annual_div['cash_dividend'],
                    text=annual_div['cash_dividend'].apply(lambda x: f"${x:.2f}"), textposition='auto', marker_color='#1f77b4'
                ))
                fig_div.update_layout(height=250, template="plotly_white", margin=dict(l=0, r=0, t=30, b=0), yaxis_title="年度現金股利 (元)")
                st.plotly_chart(fig_div, use_container_width=True)
            else:
                st.info("查無近五年現金股利資料（或該股不配息）。")
        else:
            st.info("此檔股票無歷史配息紀錄。")

        st.markdown("---")
        st.success(generate_pro_analysis(df_price, df_inst_clean, display_title, ma_fast, ma_slow))

        # --- 📈 互動技術線圖 (單一報酬率) ---
        st.write(f"### 📈 互動技術線圖 ({timeframe})")

        def get_ret(m=0, y=0):
            if len(df_price) < 5: return None
            target = df_price.index[-1] - pd.DateOffset(months=m, years=y)
            past = df_price[df_price.index >= target]
            if not past.empty: return ((current_price - past['Close'].iloc[0]) / past['Close'].iloc[0]) * 100
            return None

        if timeframe == "近一月": start_dt, period_ret = df_price.index[-1] - pd.DateOffset(months=1), get_ret(m=1)
        elif timeframe == "近三月": start_dt, period_ret = df_price.index[-1] - pd.DateOffset(months=3), get_ret(m=3)
        elif timeframe == "近半年": start_dt, period_ret = df_price.index[-1] - pd.DateOffset(months=6), get_ret(m=6)
        elif timeframe == "近一年": start_dt, period_ret = df_price.index[-1] - pd.DateOffset(years=1), get_ret(y=1)
        else: start_dt, period_ret = df_price.index[-1] - pd.DateOffset(years=5), get_ret(y=5)

        df_plot = df_price[df_price.index >= start_dt].copy()

        if period_ret is not None:
            st.markdown(f"**🎯 {timeframe} 獲利表現：** :{'red' if period_ret > 0 else 'green'}[**{period_ret:+.2f}%**]")
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        fig.add_trace(gr.Candlestick(x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name='K線', increasing=dict(line=dict(color='#ff3333'), fillcolor='#ff3333'), decreasing=dict(line=dict(color='#00b33c'), fillcolor='#00b33c')), row=1, col=1)
        fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['MA_fast'], mode='lines', name=f'{ma_fast}MA', line=dict(width=1.5, color='orange')), row=1, col=1)
        fig.add_trace(gr.Scatter(x=df_plot.index, y=df_plot['MA_slow'], mode='lines', name=f'{ma_slow}MA', line=dict(width=1.5, color='blue')), row=1, col=1)
        
        colors_vol = ['#ff3333' if df_plot['Close'].iloc[i] > df_plot['Open'].iloc[i] else '#00b33c' for i in range(len(df_plot))]
        fig.add_trace(gr.Bar(x=df_plot.index, y=df_plot['Volume'], marker_color=colors_vol, name='成交股數'), row=2, col=1)
        fig.update_layout(xaxis_rangeslider_visible=False, height=550, template="plotly_white", margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

        # --- 👥 法人買賣超 ---
        st.write("### 👥 每日三大法人買賣超明細（張）")
        if not df_inst_clean.empty:
            plot_inst = df_inst_clean.tail(30)
            fig_inst = gr.Figure()
            for col, color in zip(['外資', '投信', '自營商'], ['red', '#ff9900', 'blue']):
                fig_inst.add_trace(gr.Bar(x=plot_inst.index, y=plot_inst[col], name=col, marker_color=color))
            fig_inst.update_layout(barmode='group', height=300, template="plotly_white", margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_inst, use_container_width=True)
        else:
            st.warning("⚠️ 籌碼資料處理失敗，或今日資料尚未更新。")

        # ==========================================
        # 📰 專屬即時新聞區塊 (按時間最新排序)
        # ==========================================
        st.markdown("---")
        st.write(f"### 📰 {display_title} 相關即時新聞")
        news_list = get_stock_news(f"{stock_chinese_name} 股市")
        
        if news_list:
            for item in news_list:
                with st.expander(f"📌 {item['title']}"):
                    st.write(f"🕒 發布時間：{item['date_str']}")
                    st.markdown(f"[🔗 點擊前往閱讀完整新聞內容]({item['link']})")
        else:
            st.info("目前系統未搜尋到近期相關的新聞。")
