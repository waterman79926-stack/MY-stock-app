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

# ==========================================
# 網頁基本設定與 CSS 注入
# ==========================================
st.set_page_config(page_title="StockVision 智能台股戰情室", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    [data-testid="stHeader"] { background-color: rgba(0,0,0,0) !important; height: 0px !important; }
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { font-size: 0.85rem !important; }
    [data-testid="stVerticalBlock"] > div { padding-bottom: 0.1rem !important; }
    div[element-to-leaf="verticalblock"] > div { gap: 0.2rem !important; }
    [data-testid="collapsedControl"] { background-color: #ff4b4b !important; border-radius: 8px; padding: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: 0.3s; }
    [data-testid="collapsedControl"] svg { width: 28px !important; height: 28px !important; stroke: white !important; }
    [data-testid="collapsedControl"]:hover { background-color: #ff3333 !important; }
    .landing-title { font-size: 2.5rem; font-weight: 800; background: -webkit-linear-gradient(45deg, #ff4b4b, #ff904f); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🎨 標題與本機 Logo 自動讀取
# ==========================================
def get_logo_html():
    for filename in ["logo.png.jpg", "logo.png"]:
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return f'<img src="data:image/jpeg;base64,{b64}" width="55" style="margin-right: 15px; border-radius: 50%; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">'
    return "📈" 

st.markdown(
    f"""
    <div style="display: flex; align-items: center; margin-bottom: 0.8rem; margin-top: -10px;">
        {get_logo_html()}
        <h2 style="margin: 0; padding: 0; font-size: 2.2rem; font-weight: 800;">StockVision 智能台股戰情室</h2>
    </div>
    """,
    unsafe_allow_html=True
)

api = DataLoader()

# 強化版股票字典：包含強制字串轉換與核心備援字典
@st.cache_data(ttl=86400) 
def get_tw_stock_info():
    fallback = {
        '2330': '台積電', '2317': '鴻海', '2324': '仁寶', '4770': '上品', 
        '0050': '元大台灣50', '0056': '元大高股息', '00878': '國泰永續高股息', 
        '2603': '長榮', '2609': '陽明', '3231': '緯創', '2382': '廣達'
    }
    try:
        df_info = api.taiwan_stock_info()
        if not df_info.empty:
            df_info['stock_id'] = df_info['stock_id'].astype(str)
            res = df_info.set_index('stock_id').to_dict('index')
            return {k: v.get('stock_name', '') for k, v in res.items()}
    except:
        pass
    return fallback

stock_info_dict = get_tw_stock_info()

# ==========================================
# 📌 側邊欄：控制台設定
# ==========================================
if 'selected_stock' not in st.session_state: st.session_state.selected_stock = ''
if 'search_box' not in st.session_state: st.session_state.search_box = ''

def select_stock(stock_id):
    st.session_state.selected_stock = stock_id
    st.session_state.search_box = "" 

st.sidebar.header("📌 戰情室控制台")

st.sidebar.text_input("🔍 搜尋股票代號或名稱", key="search_box", placeholder="例如: 2330 或 仁寶")
search_val = st.session_state.search_box.strip()

if search_val:
    if search_val in stock_info_dict:
        if st.session_state.selected_stock != search_val:
            st.session_state.selected_stock = search_val
            st.rerun()
    else:
        matches = [sid for sid, name in stock_info_dict.items() if search_val in name or search_val in sid]
        if matches:
            if len(matches) == 1:
                if st.session_state.selected_stock != matches[0]:
                    st.session_state.selected_stock = matches[0]
                    st.rerun()
            else:
                st.sidebar.markdown("👉 **找到以下相關股票，請點擊檢視：**")
                for sid in matches[:10]: 
                    name = stock_info_dict.get(sid, '')
                    st.sidebar.button(f"{sid} {name}", on_click=select_stock, args=(sid,), key=f"btn_{sid}", use_container_width=True)
        else:
            st.sidebar.error("❌ 找不到相符的股票")

st.sidebar.markdown("---")

if st.session_state.selected_stock:
    current_name = stock_info_dict.get(st.session_state.selected_stock, '')
    st.sidebar.success(f"目前檢視：{st.session_state.selected_stock} {current_name}")

st.sidebar.button("🏠 回到戰情室首頁", on_click=select_stock, args=("",), use_container_width=True)

# 常用自選股
st.sidebar.write("⚡ 常用自選股：")
quick_stocks = ["0050", "2330", "2317", "2324", "4770", "00878"]
cols = st.sidebar.columns(3)
for i, stock in enumerate(quick_stocks):
    cols[i % 3].button(stock, on_click=select_stock, args=(stock,), key=f"qk_{stock}")

# 每日熱門股 (排除自選股)
st.sidebar.write("🔥 市場熱門焦點：")
hot_stocks_pool = ["2603", "3231", "2382", "1519", "2609", "3481"]
hot_stocks = [s for s in hot_stocks_pool if s not in quick_stocks][:3]
h_cols = st.sidebar.columns(3)
for i, stock in enumerate(hot_stocks):
    h_cols[i % 3].button(stock, on_click=select_stock, args=(stock,), key=f"hot_{stock}")

st.sidebar.markdown("---")
# 順序對換：圖表區間優先，均線其次
st.sidebar.subheader("📅 圖表檢視區間")
timeframe = st.sidebar.radio("選擇互動圖表範圍", ["近一月", "近三月", "近半年", "近一年", "近五年"])

st.sidebar.markdown("---")
st.sidebar.subheader("📊 均線參數設定")
ma_fast = st.sidebar.number_input("快均線 (MA)", min_value=5, max_value=60, value=5)
ma_slow = st.sidebar.number_input("慢均線 (MA)", min_value=10, max_value=240, value=20)

end_date = datetime.today().strftime('%Y-%m-%d')
start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')
selected_stock = st.session_state.selected_stock

# ==========================================
# 📊 抓取資料模組 (防幽靈數據 + 雙重備援)
# ==========================================
@st.cache_data(ttl=300) 
def get_price_data(stock_id):
    df, divs = pd.DataFrame(), pd.Series(dtype='float64')
    for suffix in [".TW", ".TWO"]:
        try:
            ticker = yf.Ticker(f"{stock_id}{suffix}")
            temp_df = ticker.history(period="5y")
            if not temp_df.empty:
                # 剔除 NaN 幽靈數據
                df = temp_df.dropna(subset=['Close']).copy()
                if not df.empty:
                    df.index = df.index.tz_localize(None)
                    try: divs = ticker.dividends
                    except: pass
                    break 
        except:
            continue
    return df, divs

@st.cache_data(ttl=1800)
def get_fundamental_data(stock_id):
    pe, pb = 'N/A', 'N/A'
    # 策略 1: FinMind
    try:
        start_dt = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')
        df = api.taiwan_stock_per_pbr_and_dividend_yield(stock_id=stock_id, start_date=start_dt)
        if not df.empty:
            pe = df.iloc[-1].get('PER', 'N/A')
            pb = df.iloc[-1].get('PBR', 'N/A')
    except: pass
    
    # 策略 2: Yahoo 備援
    if pe == 'N/A' or pb == 'N/A':
        for s in [".TW", ".TWO"]:
            try:
                inf = yf.Ticker(f"{stock_id}{s}").info
                pe = pe if pe != 'N/A' else inf.get('trailingPE', 'N/A')
                pb = pb if pb != 'N/A' else inf.get('priceToBook', 'N/A')
                if pe != 'N/A': break
            except: pass
            
    return pe, pb

@st.cache_data(ttl=300)
def get_inst_data(stock_id, start, end):
    try: return api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start, end_date=end)
    except: return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_stock_news(stock_id, stock_name):
    # 強化版精準搜尋字串
    query = f"{stock_id} {stock_name} 財經 新聞"
    url = f"https://news.google.com/rss/search?q={quote(query)}+when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response: xml_data = response.read()
        root = ET.fromstring(xml_data)
        news = []
        for item in root.findall('./channel/item'):
            title = item.find('title').text
            link = item.find('link').text
            pub_date = email.utils.parsedate_to_datetime(item.find('pubDate').text)
            news.append({'title': title, 'link': link, 'date': pub_date})
        news = sorted(news, key=lambda x: x['date'], reverse=True)[:3]
        for n in news: n['date_str'] = n['date'].strftime('%Y-%m-%d %H:%M') 
        return news
    except: return []

# 單行精煉版 AI 分析
def generate_pro_analysis(df, df_inst, stock_name, f_ma, s_ma):
    if len(df) < 20: return f"⚠️ {stock_name} 歷史資料不足，無法進行深度解析。"
    
    close, m_f, m_s = df['Close'].iloc[-1], df['MA_fast'].iloc[-1], df['MA_slow'].iloc[-1]
    rsi, macd = df['RSI'].iloc[-1], df['MACD_diff'].iloc[-1]
    
    # 趨勢
    if close > m_f > m_s: trend = f"均線呈多頭排列，下檔 ${m_s:.2f} 有強勁支撐。"
    elif close < m_f < m_s: trend = f"均線呈空頭排列，上方 ${m_f:.2f} 反壓沉重。"
    elif close > m_s: trend = f"力守生命線 ${m_s:.2f}，屬強勢高檔震盪整理。"
    else: trend = f"目前於 ${close:.2f} 附近糾結盤整，醞釀表態方向。"

    # 動能
    if rsi >= 75: mom = f"RSI 高達 {rsi:.1f} 進入超買區，慎防獲利了結賣壓。"
    elif rsi <= 25: mom = f"RSI 降至 {rsi:.1f} 嚴重超賣，短線浮現反彈契機。"
    else: mom = f"RSI 處 {rsi:.1f} 動能溫和，MACD 柱狀圖顯示{'多' if macd>0 else '空'}方佔優。"

    # 籌碼
    inst = "三大法人籌碼尚未更新，建議盤後再確認。"
    if not df_inst.empty and df.index[-1].strftime('%Y-%m-%d') in df_inst.index:
        t_inst = df_inst.loc[df.index[-1].strftime('%Y-%m-%d')]
        f_b, t_b = t_inst.get('外資', 0), t_inst.get('投信', 0)
        tot = f_b + t_b + t_inst.get('自營商', 0)
        if f_b > 0 and t_b > 0: inst = f"土洋聯手做多，同步買超 {int(f_b+t_b):,} 張，籌碼面極佳。"
        elif f_b < 0 and t_b < 0: inst = f"土洋無情雙殺，同步賣超，需嚴防主力倒貨多殺多。"
        else: inst = f"三大法人合計{'買' if tot>0 else '賣'}超 {abs(int(tot)):,} 張，主要由{'外資' if abs(f_b)>abs(t_b) else '投信'}{'撐盤' if tot>0 else '提款'}。"

    # 策略
    if close > m_s: strat = f"大趨勢看好，建議沿 ${m_s:.2f} 偏多操作，跌破前持股續抱；空手待量縮回測找買點。"
    else: strat = f"趨勢偏弱且賣壓重，建議多看少做現金為王；若搶短多需嚴格防守今日低點。"

    return (
        f"* **💡 盤後速覽**：今日收盤 **${close:.2f}**。{trend}{mom}\n"
        f"* **🕵️‍♂️ 籌碼動向**：{inst}\n"
        f"* **🎯 實戰建議**：{strat}\n"
        f"> ⚠️ **免責聲明**：AI 分析僅供歷史學術探討參考，不構成買賣建議，請自負盈虧。"
    )

# ==========================================
# 🚀 畫面呈現 (強化版首頁 vs 戰情室)
# ==========================================
if not selected_stock:
    st.markdown('<div class="landing-title">洞悉主力籌碼，精準打擊獲利。</div>', unsafe_allow_html=True)
    st.write("歡迎來到 StockVision。請在左側搜尋股票代號開始分析，或查看以下市場即時動態。")
    st.markdown("---")
    
    # 模塊 1：大盤走勢
    st.subheader("🌐 台股大盤概況 (TAIEX)")
    try:
        twii = yf.Ticker("^TWII").history(period="1mo")
        if not twii.empty:
            c_twii, p_twii = twii['Close'].iloc[-1], twii['Close'].iloc[-2]
            st.metric("台灣加權指數", f"{c_twii:,.2f}", f"{c_twii-p_twii:+.2f} ({(c_twii-p_twii)/p_twii*100:+.2f}%)")
            fig_twii = gr.Figure(gr.Scatter(x=twii.index, y=twii['Close'], mode='lines', fill='tozeroy', line_color='#ff4b4b'))
            fig_twii.update_layout(height=150, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False, template="plotly_white")
            st.plotly_chart(fig_twii, use_container_width=True)
    except: st.info("大盤資料暫時無法載入。")
    
    st.markdown("---")
    
    # 模塊 2：產業焦點 (結合你的專業領域)
    st.subheader("🔬 產業焦點：電子材料與特用化學供應鏈")
    chem_stocks = {"1717": "長興", "4729": "達興材料", "4773": "三福化", "4770": "上品"}
    c_cols = st.columns(4)
    for i, (sid, name) in enumerate(chem_stocks.items()):
        try:
            tk = yf.Ticker(f"{sid}.TW")
            hist = tk.history(period="5d")
            if len(hist) >= 2:
                c, p = hist['Close'].iloc[-1], hist['Close'].iloc[-2]
                c_cols[i].metric(f"{sid} {name}", f"${c:.2f}", f"{c-p:+.2f} ({(c-p)/p*100:+.2f}%)")
            else: c_cols[i].metric(f"{sid} {name}", "N/A", "N/A")
        except: c_cols[i].metric(f"{sid} {name}", "N/A", "N/A")

else:
    stock_chinese_name = stock_info_dict.get(selected_stock, '')
    display_title = f"{selected_stock} {stock_chinese_name}" if stock_chinese_name else selected_stock
    st.markdown(f"#### 🔍 {display_title} 深度戰情分析")
    
    with st.spinner("深度資料與基本面運算中..."):
        df_price, divs_data = get_price_data(selected_stock)
        df_raw_inst = get_inst_data(selected_stock, start_date, end_date)

    if df_price.empty:
        st.error("⚠️ 無法取得該股票資料，請稍後再試。")
    else:
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

        current_price = df_price['Close'].iloc[-1]
        prev_close = df_price['Close'].iloc[-2] if len(df_price) > 1 else current_price
        price_change = current_price - prev_close
        price_change_pct = (price_change / prev_close) * 100 if prev_close != 0 else 0
        
        def get_ret(m=0, y=0):
            if len(df_price) < 5: return None
            target = df_price.index[-1] - pd.DateOffset(months=m, years=y)
            past = df_price[df_price.index >= target]
            if not past.empty: return ((current_price - past['Close'].iloc[0]) / past['Close'].iloc[0]) * 100
            return None
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新收盤價", f"${current_price:.2f}", f"{price_change:+.2f} ({price_change_pct:+.2f}%)", delta_color="inverse")
        c2.metric("今日最高", f"${df_price['High'].iloc[-1]:.2f}")
        c3.metric("今日最低", f"${df_price['Low'].iloc[-1]:.2f}")
        c4.metric("成交張數", f"{int(df_price['Volume'].iloc[-1] / 1000):,} 張")
        
        b1, b2, b3, b4 = st.columns(4)
        pe_ratio, pb_ratio = get_fundamental_data(selected_stock)
        
        # 產業別若無資料，顯示為 依代號分類
        sector = "電子/傳產/金融"
        eps = current_price / pe_ratio if isinstance(pe_ratio, (int, float)) and pe_ratio > 0 else 'N/A'
        
        pe_str = f"{pe_ratio:.2f} 倍" if isinstance(pe_ratio, (int, float)) else "N/A"
        eps_str = f"${eps:.2f}" if isinstance(eps, (int, float)) else "N/A"
        pb_str = f"{pb_ratio:.2f} 倍" if isinstance(pb_ratio, (int, float)) else "N/A"

        b1.metric("本益比 (P/E)", pe_str)
        b2.metric("每股盈餘 (EPS估)", eps_str)
        b3.metric("股價淨值比 (P/B)", pb_str)
        b4.metric("產業類別", str(sector))
        
        st.markdown("---")
        st.success(generate_pro_analysis(df_price, df_inst_clean, stock_chinese_name if stock_chinese_name else selected_stock, ma_fast, ma_slow))

        st.write(f"### 📈 互動技術線圖 ({timeframe})")

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
        fig.update_layout(xaxis_rangeslider_visible=False, height=500, template="plotly_white", margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

        st.write("### 👥 每日三大法人買賣超明細（張）")
        if not df_inst_clean.empty:
            plot_inst = df_inst_clean.tail(30)
            fig_inst = gr.Figure()
            for col, color in zip(['外資', '投信', '自營商'], ['red', '#ff9900', 'blue']):
                fig_inst.add_trace(gr.Bar(x=plot_inst.index, y=plot_inst[col], name=col, marker_color=color))
            fig_inst.update_layout(barmode='group', height=250, template="plotly_white", margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig_inst, use_container_width=True)
        else:
            st.warning("⚠️ 籌碼資料處理失敗，或今日資料尚未更新。")

        st.markdown("---")
        col_left, col_right = st.columns([1, 1.5]) 

        with col_left:
            st.write("### 💰 歷年配息與殖利率")
            if not divs_data.empty:
                divs_df = pd.DataFrame({'date': divs_data.index, 'cash_dividend': divs_data.values})
                divs_df['year'] = pd.to_datetime(divs_df['date']).dt.year
                annual_div = divs_df.groupby('year')['cash_dividend'].sum().reset_index()
                annual_div = annual_div[annual_div['cash_dividend'] > 0].tail(5) 
                
                if not annual_div.empty:
                    latest_div = annual_div['cash_dividend'].iloc[-1]
                    avg_div = annual_div['cash_dividend'].mean()
                    
                    st.markdown(f"**{annual_div['year'].iloc[-1]}年 股利:** `${latest_div:.2f}` (殖利率: **{(latest_div/current_price)*100:.2f}%**)")
                    st.markdown(f"**近五年平均:** `${avg_div:.2f}` (平均殖利率: **{(avg_div/current_price)*100:.2f}%**)")
                    
                    fig_div = gr.Figure(gr.Bar(
                        x=annual_div['year'].astype(str) + "年", 
                        y=annual_div['cash_dividend'],
                        text=annual_div['cash_dividend'].apply(lambda x: f"${x:.2f}"), 
                        textposition='auto', 
                        marker_color='#e67e22' 
                    ))
                    fig_div.update_layout(height=280, template="plotly_white", margin=dict(l=0, r=0, t=10, b=0), bargap=0.3, yaxis_title="現金股利 (元)")
                    st.plotly_chart(fig_div, use_container_width=True)
                else:
                    st.info("查無近五年現金股利資料。")
            else:
                st.info("此檔股票無歷史配息紀錄。")

        with col_right:
            st.write(f"### 📰 相關即時新聞")
            news_list = get_stock_news(selected_stock, stock_chinese_name)
            if news_list:
                for item in news_list:
                    with st.expander(f"📌 {item['title']}", expanded=True): 
                        st.write(f"🕒 發布時間：{item['date_str']}")
                        st.markdown(f"[🔗 點擊前往閱讀完整新聞內容]({item['link']})")
            else:
                st.info("目前系統未搜尋到近期相關的新聞。")
