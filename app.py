import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import gspread 

# --- 配置 ---
SPREADSHEET_KEY = '1WCiVbP4mR7v5MgDvEeNV8YCthkTVv0rBVv1DX5YYkB1U' 

# 缓存时间 30分钟 (30 * 60 = 1800秒)
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

# --- 1. 页面配置与标题 ---
st.set_page_config(page_title="TG BOT数据看板", layout="wide")
st.title("🚀 TG BOT数据看板 (30Min更新)")
# 移除强制刷新按钮

# --- 2. 数据清洗和预处理 ---
if df_raw.empty:
    st.warning("数据表为空或加载失败。")
    st.stop()

df = df_raw.copy()
df.columns = df.columns.astype(str).str.strip()

# 统一列名映射 (基于文件内容推断)
MAPPING = {
    df.columns[0]: 'Date',
    '机器人用户名': 'BotUsername',
    '机器人备注名': 'BotNoteName',
    '绑定的产品': 'Product',
    '所属小组': 'Group',
    '咨询数': 'Consultations',
    '新增客户线索数': 'Leads',
}

df = df.rename(columns=MAPPING)
df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
df['Consultations'] = pd.to_numeric(df['Consultations'], errors='coerce').fillna(0)
df['Leads'] = pd.to_numeric(df['Leads'], errors='coerce').fillna(0)
df = df.dropna(subset=['Date'])
df = df.sort_values('Date', ascending=True)

# 动态获取时间范围
MAX_DATE = df['Date'].max().date()
MIN_DATE = df['Date'].min().date()
TODAY = MAX_DATE 

# 初始化 Session State
if 'df_filtered' not in st.session_state:
    st.session_state.df_filtered = df # 默认加载所有数据
    st.session_state.query_submitted = False
    st.session_state.current_filters = {
        'date_option': '本周',
        'group': df['Group'].dropna().unique().tolist(),
        'username': df['BotUsername'].dropna().unique().tolist(),
        'notename': df['BotNoteName'].dropna().unique().tolist(),
        'product': df['Product'].dropna().unique().tolist(),
        'start_date': TODAY - datetime.timedelta(days=TODAY.weekday()),
        'end_date': TODAY,
    }

# --- 3. 筛选功能 (Request 3, 4, 5) ---

st.sidebar.header("数据筛选 (基于最新日期: " + str(MAX_DATE) + ")")

@st.cache_data
def get_unique_list(df, col):
    # 为多选框返回列表
    return sorted(df[col].dropna().unique().tolist())

with st.sidebar.form("filter_form"):
    
    # 3.1 日期筛选 (单选)
    date_option = st.selectbox(
        "选择时间范围:",
        ("本周", "本月", "近7天", "近30天", "自定义日期"),
        key='form_date_option'
    )

    start_date = MIN_DATE
    end_date = MAX_DATE

    if date_option == "本周":
        start_date = TODAY - datetime.timedelta(days=TODAY.weekday())
        end_date = TODAY
    elif date_option == "本月":
        start_date = TODAY.replace(day=1)
        end_date = TODAY
    elif date_option == "近7天":
        start_date = TODAY - datetime.timedelta(days=6)
        end_date = TODAY
    elif date_option == "近30天":
        start_date = TODAY - datetime.timedelta(days=29)
        end_date = TODAY
    elif date_option == "自定义日期":
        date_range = st.date_input("选择日期区间", [MIN_DATE, MAX_DATE], max_value=MAX_DATE, key='form_date_range')
        if len(date_range) == 2:
            start_date = date_range[0]
            end_date = date_range[1]
    
    # 3.2 文本筛选 (多选 Request 4)
    all_groups = get_unique_list(df, 'Group')
    all_usernames = get_unique_list(df, 'BotUsername')
    all_notenames = get_unique_list(df, 'BotNoteName')
    all_products = get_unique_list(df, 'Product')
    
    col_group = st.multiselect("所属小组", all_groups, default=all_groups, key='form_group')
    col_username = st.multiselect("机器人用户名", all_usernames, default=all_usernames, key='form_username')
    col_notename = st.multiselect("机器人备注名", all_notenames, default=all_notenames, key='form_notename')
    col_product = st.multiselect("绑定的产品", all_products, default=all_products, key='form_product')
    
    # Request 5: 查询按钮
    submitted = st.form_submit_button("🔍 查询")

if submitted or not st.session_state.query_submitted:
    
    # 初始化时的默认查询
    if not submitted and not st.session_state.query_submitted:
        # 使用默认的 '本周' 筛选
        current_groups = all_groups
        current_usernames = all_usernames
        current_notenames = all_notenames
        current_products = all_products
    else:
        current_groups = col_group
        current_usernames = col_username
        current_notenames = col_notename
        current_products = col_product
    
    # 核心数据过滤逻辑：使用 isin() 处理多选
    df_filtered_temp = df[
        (df['Date'].dt.date >= start_date) & 
        (df['Date'].dt.date <= end_date) &
        (df['Group'].isin(current_groups)) &
        (df['BotUsername'].isin(current_usernames)) &
        (df['BotNoteName'].isin(current_notenames)) &
        (df['Product'].isin(current_products))
    ].copy()
    
    # 存储筛选结果和当前过滤器状态
    st.session_state.df_filtered = df_filtered_temp
    st.session_state.query_submitted = True
    st.session_state.current_filters = {
        'date_option': date_option,
        'group': current_groups,
        'username': current_usernames,
        'notename': current_notenames,
        'product': current_products,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    if submitted:
        # 如果是用户点击查询，则强制重新执行以应用筛选
        st.rerun()


# 使用 session state 中的数据进行绘图
df_filtered = st.session_state.df_filtered
current_filters = st.session_state.current_filters


# --- 4. 统计数字指标卡 (无变化) ---
st.header("📊 核心数据指标")
# ... (指标卡计算逻辑代码保持不变) ...
def get_comparison_metrics(df, today, period_days):
    """计算本期数据和对比期数据的指标"""
    current_start = today - datetime.timedelta(days=period_days - 1)
    
    if period_days == 1: 
        prev_end = today - datetime.timedelta(days=1)
        prev_start = prev_end
    else: 
        prev_end = current_start - datetime.timedelta(days=1)
        prev_start = prev_end - datetime.timedelta(days=period_days - 1)
        
    df_curr = df[(df['Date'].dt.date >= current_start) & (df['Date'].dt.date <= today)]
    df_prev = df[(df['Date'].dt.date >= prev_start) & (df['Date'].dt.date <= prev_end)]
    
    curr_leads = df_curr['Leads'].sum()
    prev_leads = df_prev['Leads'].sum()
    
    if prev_leads == 0:
        pct_change = 0.0 if curr_leads == 0 else 100.0
    else:
        pct_change = (curr_leads - prev_leads) / prev_leads * 100
        
    return curr_leads, prev_leads, pct_change

CURRENT_WEEK_START = TODAY - datetime.timedelta(days=TODAY.weekday())
CURRENT_WEEK_DAYS = (TODAY - CURRENT_WEEK_START).days + 1
week_leads, last_week_leads_raw, week_change = get_comparison_metrics(df, TODAY, CURRENT_WEEK_DAYS)

CURRENT_MONTH_START = TODAY.replace(day=1)
month_leads = df[(df['Date'].dt.date >= CURRENT_MONTH_START)]['Leads'].sum()

LAST_WEEK_START = TODAY - datetime.timedelta(days=13)
LAST_WEEK_END = TODAY - datetime.timedelta(days=7)
last_week_leads = df[(df['Date'].dt.date >= LAST_WEEK_START) & (df['Date'].dt.date <= LAST_WEEK_END)]['Leads'].sum()

today_leads, yesterday_leads, today_change = get_comparison_metrics(df, TODAY, 1)

col1, col2, col3, col4 = st.columns(4)

col1.metric("本月总线索数", f"{int(month_leads):,}")
col2.metric("上个完整周线索数", f"{int(last_week_leads):,}")

col3.metric(
    f"本周线索数 ({CURRENT_WEEK_DAYS}天)", 
    f"{int(week_leads):,}", 
    f"{week_change:.1f}% vs 上周同期", 
    delta_color="normal"
)

col4.metric(
    f"今日线索数 ({str(TODAY)})", 
    f"{int(today_leads):,}", 
    f"{today_change:.1f}% vs 昨日", 
    delta_color="normal"
)

st.markdown("---")


# --- 5. 今日机器人数据柱状图 (Request 6, 3, 1) ---
st.subheader("🤖 今日机器人表现") 

df_today = df[(df['Date'].dt.date == TODAY)]
df_today_filtered = df_today.groupby('BotNoteName')[['Consultations', 'Leads']].sum().reset_index()

# Request 3: 按咨询数高低排序 (从左往右)
df_today_filtered = df_today_filtered.sort_values('Consultations', ascending=False)
df_today_filtered = df_today_filtered[df_today_filtered['Consultations'] > 0] 

if not df_today_filtered.empty:
    max_val = max(df_today_filtered['Consultations'].max(), df_today_filtered['Leads'].max())
    
    fig6 = go.Figure(data=[
        go.Bar(name='咨询数', x=df_today_filtered['BotNoteName'], y=df_today_filtered['Consultations'], text=df_today_filtered['Consultations'], textposition='outside', marker_color='#1f77b4'),
        go.Bar(name='线索数', x=df_today_filtered['BotNoteName'], y=df_today_filtered['Leads'], text=df_today_filtered['Leads'], textposition='outside', marker_color='#ff7f0e')
    ])
    fig6.update_layout(
        barmode='group',
        title_text=f'今日 ({str(TODAY)}) 机器人咨询与线索分布',
        xaxis_title='机器人备注名',
        yaxis_title='数量',
        legend_title='指标'
    )
    # Request 1: 确保标签不被隐藏 (增加Y轴顶部留白)
    fig6.update_yaxes(range=[0, max_val * 1.1]) 
    
    st.plotly_chart(fig6, use_container_width=True)
else:
    st.info(f"今日 ({str(TODAY)}) 暂无机器人咨询数据。")

st.markdown("---")

# --- 6. 当月总咨询数和线索数折线图 (Request 7, 4, 2) ---
st.subheader("📈 当月总趋势") 

df_month = df[df['Date'].dt.date >= CURRENT_MONTH_START].groupby('Date')[['Consultations', 'Leads']].sum().reset_index()

if not df_month.empty:
    # Request 2: 横轴显示每一天的日期 (11.01, 11.02)
    df_month['日期'] = df_month['Date'].dt.strftime('%m.%d')
    # Request 4 & 8: 指标改为中文
    df_month = df_month.rename(columns={'Consultations': '咨询', 'Leads': '线索'})
    
    fig7 = px.line(df_month, x='日期', y=['咨询', '线索'], 
                   labels={'value': '数量', 'variable': '指标'},
                   title=f"{CURRENT_MONTH_START.strftime('%Y年%m月')} 总咨询与线索趋势")
    
    # Request 8: 显示数据标签
    for trace in fig7.data:
        if trace.name in ['咨询', '线索']:
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


# --- 7. 所选产品本月趋势 (Request 9) ---
current_product_list = current_filters['product']
# 仅当筛选结果为单个产品时才显示趋势图，否则无法合理绘图
if len(current_product_list) == 1:
    current_product = current_product_list[0]
else:
    current_product = None

# 替换图标以提高兼容性
st.subheader(f"📊 产品趋势分析: {current_product if current_product else '请在侧边栏选择单个产品进行分析'}")

if current_product:
    df_product_month = df[
        (df['Date'].dt.date >= CURRENT_MONTH_START) &
        (df['Product'] == current_product)
    ].groupby('Date')[['Consultations', 'Leads']].sum().reset_index()
    
    if not df_product_month.empty:
        df_product_month['日期'] = df_product_month['Date'].dt.strftime('%m.%d')
        df_product_month = df_product_month.rename(columns={'Consultations': '咨询', 'Leads': '线索'})

        fig9 = px.line(df_product_month, x='日期', y=['咨询', '线索'], 
                       labels={'value': '数量', 'variable': '指标'},
                       title=f"{current_product} 当月咨询与线索趋势")
        
        # Request 8: 显示数据标签
        for trace in fig9.data:
            if trace.name in ['咨询', '线索']:
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
        st.info(f"产品 {current_product} 当月暂无数据。")
else:
    st.info("要查看趋势，请在侧边栏的【绑定的产品】中，选择且仅选择一个产品。")


# --- 8. 查看源数据 (Request 10) ---
st.markdown("---")
date_filter_display = f"{current_filters['start_date'].strftime('%Y-%m-%d')} 至 {current_filters['end_date'].strftime('%Y-%m-%d')}"
group_display = ', '.join(current_filters['group'])
product_display = ', '.join(current_filters['product'])


with st.expander(f"查看源数据 (筛选区间: {date_filter_display} / 小组: {group_display} / 产品: {product_display})", expanded=False):
    st.dataframe(df_filtered.sort_values('Date', ascending=True), use_container_width=True)
