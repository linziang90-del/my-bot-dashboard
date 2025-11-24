import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import gspread 

# --- 配置 ---
# 请确保您的 SPREADSHEET_KEY 是正确的
SPREADSHEET_KEY = '1WCiVbP4mR7v5MgDvEeNV8YCthkTVv0rBVv1DX5YYkB1U' 

# 缓存时间 30分钟
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
df = load_data()

# --- 2. 数据清洗和预处理 (全局数据，用于 Request 5) ---
if df.empty:
    st.title("🚀 TG BOT数据看板 (30Min更新)")
    st.warning("数据表为空或加载失败。")
    st.stop()

df.columns = df.columns.astype(str).str.strip()
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

# 初始化 Session State (用于存储 Product Trend 筛选条件)
if 'product_filters' not in st.session_state:
    all_groups = df['Group'].dropna().unique().tolist()
    all_usernames = df['BotUsername'].dropna().unique().tolist()
    all_notenames = df['BotNoteName'].dropna().unique().tolist()
    all_products = df['Product'].dropna().unique().tolist()
    
    st.session_state.product_filters = {
        'date_option': '本月',
        'group': all_groups,
        'username': all_usernames,
        'notename': all_notenames,
        'product': all_products,
        'start_date': TODAY.replace(day=1), # 默认本月
        'end_date': TODAY,
    }
    st.session_state.query_submitted = False

# --- 3. 页面配置与标题 ---
st.set_page_config(page_title="TG BOT数据看板", layout="wide")
st.title("🚀 TG BOT数据看板 (30Min更新)")
st.markdown(f"**数据更新至：{str(TODAY)}**")

# --- 4. 核心数据指标 (Request 5 - 不受筛选控制) ---
st.header("📊 核心数据指标")

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


# --- 5. 今日机器人数据柱状图 (Request 5 - 不受筛选控制) ---
st.header("🤖 今日机器人表现") 

df_today = df[(df['Date'].dt.date == TODAY)]
df_today_filtered = df_today.groupby('BotNoteName')[['Consultations', 'Leads']].sum().reset_index()
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

# --- 6. 当月总趋势折线图 (Request 5 - 不受筛选控制) ---
st.header("📈 当月总趋势") 

df_month = df[df['Date'].dt.date >= CURRENT_MONTH_START].groupby('Date')[['Consultations', 'Leads']].sum().reset_index()

if not df_month.empty:
    # Request 2: 日期格式修正
    df_month['日期'] = df_month['Date'].dt.strftime('%m.%d')
    df_month = df_month.rename(columns={'Consultations': '咨询', 'Leads': '线索'})
    
    fig7 = px.line(df_month, x='日期', y=['咨询', '线索'], 
                   labels={'value': '数量', 'variable': '指标'},
                   title=f"{CURRENT_MONTH_START.strftime('%Y年%m月')} 总咨询与线索趋势")
    
    for trace in fig7.data:
        if trace.name in ['咨询', '线索']:
            fig7.add_trace(go.Scatter(
                x=trace.x, y=trace.y, mode='text', 
                text=[f'{int(val)}' for val in trace.y], 
                textposition='top center', 
                name=trace.name + ' 标签', showlegend=False, marker=dict(size=0)
            ))
    # Request 1: 强制显示所有日期标签，避免重叠
    fig7.update_xaxes(tickangle=45) 
    
    st.plotly_chart(fig7, use_container_width=True)
else:
    st.info("当月暂无数据。")

st.markdown("---")


# ====================================================================
# --- 7. 产品趋势分析筛选 (Request 6: 筛选区域) ---
# ====================================================================

st.header("📊 产品趋势分析筛选")

@st.cache_data
def get_unique_list(df, col):
    return sorted(df[col].dropna().unique().tolist())

all_groups = get_unique_list(df, 'Group')
all_usernames = get_unique_list(df, 'BotUsername')
all_notenames = get_unique_list(df, 'BotNoteName')
all_products = get_unique_list(df, 'Product')

# 使用 columns 布局筛选条件，更紧凑
cols = st.columns(5) 

with st.form("product_trend_form"):
    
    # --- 日期筛选 (Request 4 default: 本月) ---
    with cols[0]:
        date_option = st.selectbox(
            "时间范围:",
            ("本月", "本周", "近7天", "近30天", "自定义日期"),
            key='form_date_option'
        )

    # --- 组合筛选 (多选 Request 4) ---
    with cols[1]:
        col_group = st.multiselect("所属小组", all_groups, default=all_groups, key='form_group')
    with cols[2]:
        col_username = st.multiselect("机器人用户名", all_usernames, default=all_usernames, key='form_username')
    with cols[3]:
        col_notename = st.multiselect("机器人备注名", all_notenames, default=all_notenames, key='form_notename')
    with cols[4]:
        col_product = st.multiselect("绑定的产品", all_products, default=all_products, key='form_product')
    
    # --- 日期范围输入 (自定义) ---
    start_date = MIN_DATE
    end_date = TODAY

    if date_option == "本月":
        start_date = TODAY.replace(day=1)
    elif date_option == "本周":
        start_date = TODAY - datetime.timedelta(days=TODAY.weekday())
    elif date_option == "近7天":
        start_date = TODAY - datetime.timedelta(days=6)
    elif date_option == "近30天":
        start_date = TODAY - datetime.timedelta(days=29)
    elif date_option == "自定义日期":
        st.caption("自定义日期区间:")
        date_range_cols = st.columns(2)
        with date_range_cols[0]:
            start_date = st.date_input("起始日期", MIN_DATE, key='form_start_date', max_value=MAX_DATE, label_visibility="collapsed")
        with date_range_cols[1]:
            end_date = st.date_input("结束日期", TODAY, key='form_end_date', max_value=MAX_DATE, label_visibility="collapsed")


    submitted = st.form_submit_button("🔍 查询趋势")


# --- 8. 执行筛选 (Request 4) ---

# 初始化 / 提交逻辑
if submitted or not st.session_state.query_submitted:
    
    # 核心数据过滤逻辑
    df_product_filtered_temp = df[
        (df['Date'].dt.date >= start_date) & 
        (df['Date'].dt.date <= end_date) &
        (df['Group'].isin(col_group)) &
        (df['BotUsername'].isin(col_username)) &
        (df['BotNoteName'].isin(col_notename)) &
        (df['Product'].isin(col_product))
    ].copy()
    
    # 存储筛选结果和当前过滤器状态
    st.session_state.df_product_filtered = df_product_filtered_temp
    st.session_state.query_submitted = True
    st.session_state.product_filters = {
        'date_option': date_option,
        'group': col_group,
        'username': col_username,
        'notename': col_notename,
        'product': col_product,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    if submitted:
        st.rerun()

# 使用 Session State 中的数据
df_product_filtered = st.session_state.df_product_filtered
current_product_filters = st.session_state.product_filters


# --- 9. 产品趋势分析 (Request 3) ---
current_product_list = current_product_filters['product']

st.markdown("---")
st.subheader(f"📊 趋势分析 (时间: {current_product_filters['start_date'].strftime('%m.%d')} - {current_product_filters['end_date'].strftime('%m.%d')})")

if len(current_product_list) == 1:
    current_product = current_product_list[0]
    
    df_product_month = df_product_filtered.groupby('Date')[['Consultations', 'Leads']].sum().reset_index()
    
    if not df_product_month.empty:
        # Request 3: 日期格式修正
        df_product_month['日期'] = df_product_month['Date'].dt.strftime('%m.%d')
        df_product_month = df_product_month.rename(columns={'Consultations': '咨询', 'Leads': '线索'})

        fig9 = px.line(df_product_month, x='日期', y=['咨询', '线索'], 
                       labels={'value': '数量', 'variable': '指标'},
                       title=f"产品: {current_product} 趋势")
        
        for trace in fig9.data:
            if trace.name in ['咨询', '线索']:
                fig9.add_trace(go.Scatter(
                    x=trace.x, y=trace.y, mode='text', 
                    text=[f'{int(val)}' for val in trace.y], 
                    textposition='top center', 
                    name=trace.name + ' 标签', showlegend=False, marker=dict(size=0)
                ))
        
        # Request 3: 强制显示所有日期标签，避免重叠
        fig9.update_xaxes(tickangle=45) 
        
        st.plotly_chart(fig9, use_container_width=True)
    else:
        st.info(f"当前筛选条件下，产品 {current_product} 暂无数据。")

elif len(current_product_list) > 1:
    st.warning(f"已选择 **{len(current_product_list)}** 个产品。趋势分析图只支持查看 **单个产品** 的趋势。请在上方【绑定的产品】中，选择且仅选择一个产品。")

else:
    st.info("请在上方【绑定的产品】中至少选择一个产品。")

# --- 10. 查看源数据 (Request 4) ---
st.markdown("---")
date_filter_display = f"{current_product_filters['start_date'].strftime('%Y-%m-%d')} 至 {current_product_filters['end_date'].strftime('%Y-%m-%d')}"
group_display = f"小组: {', '.join(current_product_filters['group'])}"
product_display = f"产品: {', '.join(current_product_filters['product'])}"


with st.expander(f"查看源数据 (筛选条件: {current_product_filters['date_option']} / {group_display} / {product_display})", expanded=False):
    st.dataframe(df_product_filtered.sort_values('Date', ascending=True), use_container_width=True)
