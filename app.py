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
    .landing-title { font-size: 3rem; font-weight: 800; background: -webkit-linear-gradient(45deg, #ff4b4b, #ff904f); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 1rem; }
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

# 修正 1：強制將 stock_id 轉為字串，徹底解決 2324 搜尋不到的 Bug
@st.cache_data(ttl=86400) 
def get_tw_stock_info():
    try:
        df_info = api.taiwan_stock_info()
        df_info['stock_id'] = df_info['stock_id'].astype(str) 
        return df_info.set_index('stock_id').to_dict('index')
    except:
        return {}

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
        matches = [sid for sid, data in stock_info_dict.items() if search_val in str(data.get('stock_name', '')) or search_val in sid]
        if matches:
            if len(matches) == 1:
                if st.session_state.selected_stock != matches[0]:
                    st.session_state.selected_stock = matches[0]
                    st.rerun()
            else:
                st.sidebar.markdown("👉 **找到以下相關股票，請點擊檢視：**")
                for sid in matches[:15]: 
                    name = stock_info_dict[sid].get('stock_name', '')
                    st.sidebar.button(f"{sid} {name}", on_click=select_stock, args=(sid,), key=f"btn_{sid}", use_container_width=True)
        else:
            st.sidebar.error("❌ 找不到相符的股票")

st.sidebar.markdown("---")

if st.session_state.selected_stock:
    current_name = stock_info_dict.get(st.session_state.selected_stock, {}).get('stock_name', '')
    st.sidebar.success(f"目前檢視：{st.session_state.selected_stock} {current_name}")

st.sidebar.button("🏠 回到戰情室首頁", on_click=select_stock, args=("",), use_container_width=True)

st.sidebar.write("⚡ 常用自選股：")
quick_stocks = ["0050", "2330", "2317", "2324", "00878", "0056"]
cols = st.sidebar.columns(3)
for i, stock in enumerate(quick_stocks):
    cols[i % 3].button(stock, on_click=select_stock, args=(stock,), key=f"qk_{stock}")

st.sidebar.markdown("---")
st.sidebar.subheader("📊 均線參數設定")
ma_fast = st.sidebar.number_input("快均線 (MA)", min_value=5, max_value=60, value=5)
ma_slow = st.sidebar.number_input("慢均線 (MA)", min_value=10, max_value=240, value=20)

st.sidebar.markdown("---")
st.sidebar.subheader("📅 圖表檢視區間")
timeframe = st.sidebar.radio("選擇互動圖表範圍", ["近一月", "近三月", "近半年", "近一年", "近五年"])

st.sidebar.markdown("---")
st.sidebar.subheader("☕ 支持開發者")
st.sidebar.caption("如果這個戰情室幫您避開了大跌，歡迎請我喝杯咖啡！")
bmc_html = """
<div style="text-align: center; margin-top: 10px;">
    <a href="https://ko-fi.com/" target="_blank">
        <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 45px !important;width: 162px !important;" >
    </a>
</div>
"""
st.sidebar.markdown(bmc_html, unsafe_allow_html=True)

end_date = datetime.today().strftime('%Y-%m-%d')
start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')
selected_stock = st.session_state.selected_stock

# ==========================================
# 📊 抓取資料模組 
# ==========================================
@st.cache_data(ttl=300) 
def get_price_data(stock_id):
    df, divs = pd.DataFrame(), pd.Series(dtype='float64')
    for suffix in [".TW", ".TWO"]:
        try:
            ticker = yf.Ticker(f"{stock_id}{suffix}")
            temp_df = ticker.history(period="5y")
            # 修正 2：加入 .dropna(subset=['Close']) 剔除 NaN 幽靈數據
            if not temp_df.empty:
                df = temp_df.dropna(subset=['Close']).copy()
                if not df.empty:
                    df.index = df.index.tz_localize(None)
                    try: divs = ticker.dividends
                    except: pass
                    break 
        except:
            continue
    return df, divs

@st.cache_data(ttl=86400)
def get_fundamental_data(stock_id):
    try:
        start_dt = (datetime.today() - timedelta(days=14)).strftime('%Y-%m-%d')
        df = api.taiwan_stock_per_pbr_and_dividend_yield(stock_id=stock_id, start_date=start_dt)
        if not df.empty:
            latest = df.iloc[-1]
            return latest.get('PER', 'N/A'), latest.get('PBR', 'N/A')
    except:
        pass
    return 'N/A', 'N/A'

@st.cache_data(ttl=300)
def get_inst_data(stock_id, start, end):
    try: return api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start, end_date=end)
    except: return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_stock_news(query):
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

# 修正 3：進階版 AI 分析引擎 (動態代入具體點位與獨特語氣)
def generate_pro_analysis(df, df_inst, stock_name, f_ma, s_ma):
    if len(df) < 20: return f"⚠️ {stock_name} 的歷史資料不足，無法進行深度的技術面與籌碼解析。"
    
    close = df['Close'].iloc[-1]
    ma_f_val, ma_s_val = df['MA_fast'].iloc[-1], df['MA_slow'].iloc[-1]
    rsi = df['RSI'].iloc[-1]
    macd_hist = df['MACD_diff'].iloc[-1]
    macd_hist_prev = df['MACD_diff'].iloc[-2]
    
    # 趨勢動態判斷
    if close > ma_f_val > ma_s_val: 
        trend = f"技術面展現強勢『多頭排列』，目前股價站穩 {f_ma} 日線之上。下方 {s_ma} 日線（約 ${ma_s_val:.2f}）已形成長線強力支撐。"
    elif close < ma_f_val < ma_s_val: 
        trend = f"目前線型落入『空頭排列』，上檔 {f_ma} 日線（約 ${ma_f_val:.2f}）形成沉重反壓，空方主導盤勢，尚未見到止跌訊號。"
    elif close > ma_s_val and close < ma_f_val: 
        trend = f"短期雖跌破 {f_ma} 日線（${ma_f_val:.2f}），但仍力守生命線（${ma_s_val:.2f}），屬於『高檔強勢震盪整理』，正在醞釀下一波表態。"
    else: 
        trend = f"均線呈現糾結狀態，目前股價在 ${close:.2f} 附近狹幅盤整，主力似乎還在觀望，缺乏明確的突破方向。"

    # 動能與 RSI 具體數值寫入
    if rsi >= 80: momentum = f"特別注意，RSI 已狂飆至 {rsi:.1f} 的極度超買區，隨時可能湧現獲利了結賣壓！"
    elif rsi >= 65: momentum = f"RSI 來到 {rsi:.1f} 的強勢區間，多頭動能依然充沛。"
    elif rsi <= 25: momentum = f"RSI 嚴重超賣降至 {rsi:.1f}，短線上已浮現跌深反彈的黃金契機。"
    elif rsi <= 40: momentum = f"指標顯示買氣疲弱 (RSI {rsi:.1f})，仍在弱勢探底。"
    else:
        if macd_hist > 0 and macd_hist > macd_hist_prev: momentum = "搭配 MACD 紅柱持續放大，顯示多方攻擊的火種正在延燒。"
        elif macd_hist < 0 and macd_hist < macd_hist_prev: momentum = "MACD 綠柱擴散，空方下殺動能有增強趨勢，需提高警覺。"
        else: momentum = f"動能指標相對溫和 (RSI 處於 {rsi:.1f} 中性區)，爆發力道暫歇。"

    # 籌碼動態判斷
    inst_comment = "今日三大法人籌碼尚未結算更新，建議尾盤或盤後再做最後確認。"
    if not df_inst.empty and df.index[-1].strftime('%Y-%m-%d') in df_inst.index:
        today_inst = df_inst.loc[df.index[-1].strftime('%Y-%m-%d')]
        f_buy, t_buy, d_buy = today_inst.get('外資', 0), today_inst.get('投信', 0), today_inst.get('自營商', 0)
        total = f_buy + t_buy + d_buy
        
        if f_buy > 0 and t_buy > 0: 
            inst_comment = f"籌碼面極佳！【土洋聯手做多】，外資與投信今日同步買超共 {int(f_buy+t_buy):,} 張，大戶籌碼高度集中，對後續推升極為有利。"
        elif f_buy < 0 and t_buy < 0: 
            inst_comment = f"警訊！【土洋無情雙殺】，外資與投信今日同步倒貨，大戶偏空操作，必須嚴防籌碼鬆動引發的多殺多。"
        elif total > 0: 
            main_buyer = '外資' if f_buy > t_buy else '投信'
            inst_comment = f"三大法人合計偏多操作，買超 {int(total):,} 張，背後主要由『{main_buyer}』進場撐盤護盤。"
        else: 
            inst_comment = f"三大法人整體偏向提款，合計賣超 {abs(int(total)):,} 張，顯示法人大戶現階段操作心態相當保守。"

    # 策略加入具體價格位階
    if close > ma_s_val: 
        strategy = f"【順勢偏多】目前 {stock_name} 大趨勢依舊看好。建議以 ${ma_s_val:.2f} 作為波段防守底線，只要不跌破就持股續抱，讓獲利奔跑；空手者可等量縮回測時再找買點，切忌盲目追高。"
    else: 
        strategy = f"【風險控管】現階段上方賣壓沉重，趨勢明顯轉弱。強烈建議多看少做，現金為王；若手癢想搶短多反彈，必須嚴格把今天的低點當作停損防守線。"

    disclaimer = "\n> ⚠️ **免責聲明**：以上 AI 解析僅供歷史學術探討，不構成任何買賣推薦或投資建議，進場前請獨立思考並自負盈虧。"

    return (
        f"* **💡 盤後重點速覽**：{stock_name} 今日收在 **${close:.2f}**。{trend} {momentum}\n"
        f"* **🕵️‍♂️ 籌碼追蹤動向**：{inst_comment}\n"
        f"* **🎯 AI 實戰操作建議**：{strategy}\n"
        f"{disclaimer}"
    )

# ==========================================
# 🚀 畫面呈現 
# ==========================================
if not selected_stock:
    st.markdown('<div class="landing-title">洞悉主力籌碼，精準打擊獲利。</div>', unsafe_allow_html=True)
    st.write("### 歡迎來到 StockVision 智能台股戰情室")
    st.write("這是一個專為現代投資人打造的無廣告、高流暢度看盤系統。請在左側 **「戰情室控制台」** 輸入股票代號或中文名稱開始分析。")
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("#### 🤖 專屬 AI 盤後解析\n系統每日自動計算各項精準數據，AI 分析師依據技術面與籌碼面為您產出具有靈魂的實戰策略指引。")
    with col2:
        st.success("#### 🕵️‍♂️ 三大法人籌碼追蹤\n直觀的柱狀圖設計，中英文雙重關鍵字模糊防護，一眼看穿外資、投信與自營商的每日對作動向。")
    with col3:
        st.warning("#### 💰 歷年配息與基本面\n左右雙欄精煉設計，一鍵精算現價殖利率，並整合最新 Google 財經即時新聞與核心財務指標。")

else:
    stock_chinese_name = stock_info_dict.get(selected_stock, {}).get('stock_name', '')
    display_title = f"{selected_stock} {stock_chinese_name}" if stock_chinese_name else selected_stock
    
    st.markdown(f"#### 🔍 {display_title} 深度戰情分析")
    
    with st.spinner("深度資料與基本面運算中..."):
        df_price, divs_data = get_price_data(selected_stock)
        df_raw_inst = get_inst_data(selected_stock, start_date, end_date)

    if df_price.empty:
        st.error("⚠️ 無法取得該股票資料，可能是代號錯誤，或是伺服器暫時阻擋連線，請稍等幾分鐘後再試。")
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
        sector = stock_info_dict.get(selected_stock, {}).get('industry_category', 'N/A')
        
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
            news_list = get_stock_news(f"{stock_chinese_name} 股市")
            if news_list:
                for item in news_list:
                    with st.expander(f"📌 {item['title']}", expanded=True): 
                        st.write(f"🕒 發布時間：{item['date_str']}")
                        st.markdown(f"[🔗 點擊前往閱讀完整新聞內容]({item['link']})")
            else:
                st.info("目前系統未搜尋到近期相關的新聞。")
