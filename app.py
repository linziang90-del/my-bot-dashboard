import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import gspread 

# --- 配置 ---
SPREADSHEET_KEY = '1WCiVbP4mR7v5MgDvEeNV8YCthkTVv0rBVv1DX5YkB1U' 

# 30分钟缓存 (30 * 60 = 1800秒)
@st.cache_data(ttl=1800) 
def load_data():
    """连接 Google Sheets 并加载数据"""
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("未配置 Secrets！请在 Streamlit Cloud 后台配置 gcp_service_account。")
            st.stop()
            
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)

        sh = gc.open_by_key(SPREADSHEET_KEY)
        worksheet = sh.sheet1 
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"❌ 数据加载失败，请检查 Google Sheets 权限。详细错误: {e}")
        st.stop()
        return pd.DataFrame()

# 核心数据加载
df_raw = load_data()

# --- 2. 标题和基本设置 ---
# Request 2: 更改标题
st.set_page_config(page_title="TG BOT数据看板", layout="wide")
st.title("🚀 TG BOT数据看板 (30Min更新)")

# Request 3: 移除数据源链接
# st.markdown("数据源：[点击查看 Google Sheets 原表]...") 

# 添加刷新按钮 (来自上一个回复的优化)
col_header, col_btn = st.columns([6, 1])
with col_btn:
    if st.button("🔄 强制刷新数据"):
        st.cache_data.clear()
        st.rerun()

# --- 3. 数据清洗和预处理 ---
if df_raw.empty:
    st.warning("数据表为空或加载失败。")
    st.stop()

df = df_raw.copy()
df.columns = df.columns.astype(str).str.strip()

# 统一列名映射 (根据提供的文件片段)
MAPPING = {
    df.columns[0]: 'Date',
    '机器人用户名': 'BotUsername',
    '机器人备注名': 'BotNoteName',
    '绑定的产品': 'Product',
    '所属小组': 'Group',
    '咨询数': 'Consultations',
    '新增客户线索数': 'Leads',
}

# 应用重命名并处理日期和数字
df = df.rename(columns=MAPPING)
df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
df['Consultations'] = pd.to_numeric(df['Consultations'], errors='coerce').fillna(0)
df['Leads'] = pd.to_numeric(df['Leads'], errors='coerce').fillna(0)
df = df.dropna(subset=['Date'])
df = df.sort_values('Date', ascending=True)

# 动态获取时间范围
MAX_DATE = df['Date'].max().date()
MIN_DATE = df['Date'].min().date()
TODAY = MAX_DATE # 将最新数据日期视为今日

# --- 4. 筛选功能优化 (Request 1) ---

st.sidebar.header("数据筛选 (基于最新日期: " + str(MAX_DATE) + ")")

# 4.1 日期筛选
date_option = st.sidebar.selectbox(
    "选择时间范围:",
    ("本周", "本月", "近7天", "近30天", "自定义日期")
)

start_date = MIN_DATE
end_date = MAX_DATE

if date_option == "本周":
    start_date = TODAY - datetime.timedelta(days=TODAY.weekday())
elif date_option == "本月":
    start_date = TODAY.replace(day=1)
elif date_option == "近7天":
    start_date = TODAY - datetime.timedelta(days=6)
elif date_option == "近30天":
    start_date = TODAY - datetime.timedelta(days=29)
elif date_option == "自定义日期":
    date_range = st.sidebar.date_input("选择日期区间", [MIN_DATE, MAX_DATE], max_value=MAX_DATE)
    if len(date_range) == 2:
        start_date = date_range[0]
        end_date = date_range[1]

# 4.2 文本筛选 (支持输入和选择)
@st.cache_data
def get_unique_list(df, col):
    return ['全部'] + sorted(df[col].dropna().unique().tolist())

col_group = st.sidebar.selectbox("所属小组", get_unique_list(df, 'Group'))
col_username = st.sidebar.selectbox("机器人用户名", get_unique_list(df, 'BotUsername'))
col_notename = st.sidebar.selectbox("机器人备注名", get_unique_list(df, 'BotNoteName'))
col_product = st.sidebar.selectbox("绑定的产品", get_unique_list(df, 'Product'))

# 核心数据过滤
df_filtered = df[
    (df['Date'].dt.date >= start_date) & 
    (df['Date'].dt.date <= end_date) &
    (df['Group'] == col_group if col_group != '全部' else True) &
    (df['BotUsername'] == col_username if col_username != '全部' else True) &
    (df['BotNoteName'] == col_notename if col_notename != '全部' else True) &
    (df['Product'] == col_product if col_product != '全部' else True)
].copy()

# --- 5. 统计数字指标卡 (Request 4) ---
st.header("📊 核心数据指标")

def get_comparison_metrics(df, today, period_days):
    """计算本期数据和对比期数据的指标"""
    current_start = today - datetime.timedelta(days=period_days - 1)
    
    # 调整对比期起始日期
    if period_days == 1: # 对比昨日
        prev_end = today - datetime.timedelta(days=1)
        prev_start = prev_end
    else: # 对比上个周期
        prev_end = current_start - datetime.timedelta(days=1)
        prev_start = prev_end - datetime.timedelta(days=period_days - 1)
        
    df_curr = df[(df['Date'].dt.date >= current_start) & (df['Date'].dt.date <= today)]
    df_prev = df[(df['Date'].dt.date >= prev_start) & (df['Date'].dt.date <= prev_end)]
    
    curr_leads = df_curr['Leads'].sum()
    prev_leads = df_prev['Leads'].sum()
    
    # 计算百分比变化
    if prev_leads == 0:
        pct_change = 0.0 if curr_leads == 0 else 100.0
    else:
        pct_change = (curr_leads - prev_leads) / prev_leads * 100
        
    return curr_leads, pct_change

# --- 时间段定义 ---
# 本周 (周一到今天)
CURRENT_WEEK_START = TODAY - datetime.timedelta(days=TODAY.weekday())
CURRENT_WEEK_DAYS = (TODAY - CURRENT_WEEK_START).days + 1
week_leads, week_change = get_comparison_metrics(df, TODAY, CURRENT_WEEK_DAYS)

# 本月 (1号到今天)
CURRENT_MONTH_START = TODAY.replace(day=1)
month_leads = df[(df['Date'].dt.date >= CURRENT_MONTH_START)]['Leads'].sum()

# 昨日 (固定7天周期)
LAST_WEEK_START = TODAY - datetime.timedelta(days=13)
LAST_WEEK_END = TODAY - datetime.timedelta(days=7)
last_week_leads = df[(df['Date'].dt.date >= LAST_WEEK_START) & (df['Date'].dt.date <= LAST_WEEK_END)]['Leads'].sum()

# 今日 (固定1天周期)
today_leads, today_change = get_comparison_metrics(df, TODAY, 1)

# --- 指标卡展示 ---
col1, col2, col3, col4 = st.columns(4)

col1.metric("本月线索数", f"{int(month_leads):,}")
col2.metric("上周线索数", f"{int(last_week_leads):,}")

col3.metric(
    f"本周线索数 ({CURRENT_WEEK_DAYS}天)", 
    f"{int(week_leads):,}", 
    f"{week_change:.1f}% vs 上周", 
    delta_color="normal"
)

col4.metric(
    f"今日线索数 ({str(TODAY)})", 
    f"{int(today_leads):,}", 
    f"{today_change:.1f}% vs 昨日", 
    delta_color="normal"
)

st.markdown("---")


# --- 6. 今日机器人数据柱状图 (Request 6) ---
st.subheader("🤖 今日机器人表现 (咨询 > 0)")

df_today = df[(df['Date'].dt.date == TODAY)]
df_today_filtered = df_today[df_today['Consultations'] > 0].groupby('BotNoteName')[['Consultations', 'Leads']].sum().reset_index()

if not df_today_filtered.empty:
    fig6 = go.Figure(data=[
        go.Bar(name='咨询数', x=df_today_filtered['BotNoteName'], y=df_today_filtered['Consultations'], text=df_today_filtered['Consultations'], textposition='outside'),
        go.Bar(name='线索数', x=df_today_filtered['BotNoteName'], y=df_today_filtered['Leads'], text=df_today_filtered['Leads'], textposition='outside')
    ])
    fig6.update_layout(
        barmode='group',
        title_text='今日机器人咨询与线索分布',
        xaxis_title='机器人备注名',
        yaxis_title='数量',
        legend_title='指标'
    )
    st.plotly_chart(fig6, use_container_width=True)
else:
    st.info(f"今日 ({str(TODAY)}) 暂无机器人咨询数据 (咨询数需大于0)。")

st.markdown("---")

# --- 7. 当月总咨询数和线索数折线图 (Request 7) ---
st.subheader("📈 当月总趋势 (咨询与线索)")

df_month = df[df['Date'].dt.date >= CURRENT_MONTH_START].groupby('Date')[['Consultations', 'Leads']].sum().reset_index()

if not df_month.empty:
    # 确保日期列用于绘图
    df_month['DateStr'] = df_month['Date'].dt.strftime('%Y-%m-%d')
    fig7 = px.line(df_month, x='DateStr', y=['Consultations', 'Leads'], 
                   labels={'value': '数量', 'variable': '指标', 'DateStr': '日期'},
                   title=f"{CURRENT_MONTH_START.strftime('%Y年%m月')} 总咨询与线索趋势")
    
    # Request 8: 显示数据标签
    for trace in fig7.data:
        fig7.add_trace(go.Scatter(
            x=trace.x, 
            y=trace.y, 
            mode='text', 
            text=[f'{int(val)}' for val in trace.y], 
            textposition='top center', 
            name=trace.name + ' 标签',
            showlegend=False,
            marker=dict(size=0)
        ))
    
    st.plotly_chart(fig7, use_container_width=True)
else:
    st.info("当月暂无数据。")

st.markdown("---")


# --- 8. 所选产品本月趋势 (Request 9) ---
st.subheader(f"🌐 产品趋势分析: {col_product if col_product != '全部' else '请在侧边栏选择产品'}")

if col_product != '全部':
    df_product_month = df[
        (df['Date'].dt.date >= CURRENT_MONTH_START) &
        (df['Product'] == col_product)
    ].groupby('Date')[['Consultations', 'Leads']].sum().reset_index()
    
    if not df_product_month.empty:
        df_product_month['DateStr'] = df_product_month['Date'].dt.strftime('%Y-%m-%d')
        fig9 = px.line(df_product_month, x='DateStr', y=['Consultations', 'Leads'], 
                       labels={'value': '数量', 'variable': '指标', 'DateStr': '日期'},
                       title=f"{col_product} 当月咨询与线索趋势")
        
        # Request 8: 显示数据标签
        for trace in fig9.data:
            fig9.add_trace(go.Scatter(
                x=trace.x, 
                y=trace.y, 
                mode='text', 
                text=[f'{int(val)}' for val in trace.y], 
                textposition='top center', 
                name=trace.name + ' 标签',
                showlegend=False,
                marker=dict(size=0)
            ))
            
        st.plotly_chart(fig9, use_container_width=True)
    else:
        st.info(f"产品 {col_product} 当月暂无数据。")
else:
    st.info("请在侧边栏选择一个特定的产品进行趋势分析。")


# --- 9. 查看源数据 (Request 10) ---
st.markdown("---")
# Request 5: 筛选结果应用于整个看板，因此不需要额外的机器人选择器。

with st.expander(f"查看源数据 ({date_option} - {col_group} {col_product})", expanded=False):
    # Request 10: 表格需要为日期升序排序 (已在df_filtered中实现)
    st.dataframe(df_filtered.sort_values('Date', ascending=True), use_container_width=True)
