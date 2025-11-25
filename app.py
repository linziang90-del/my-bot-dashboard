import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import gspread 

# --- 配置 ---
SPREADSHEET_KEY = '1WCiVbP4mR7v5MgDvEeNV8YCthkTVv0rBVv1DX5YkB1U' 

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
        st.error(f"❌ 数据加载失败，请检查 Google Sheets 权限或 Key。详细错误: {e}")
        st.stop()
        return pd.DataFrame()

# 核心数据加载
df = load_data()

# --- 2. 数据清洗和预处理 ---
if df.empty:
    st.set_page_config(page_title="TG BOT数据看板", layout="wide")
    st.title("🚀 TG BOT数据看板") # 默认标题
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

# ==============================================================================
# 🔥 时间变量计算
# ==============================================================================
MAX_DATE = df['Date'].max().date()
MIN_DATE = df['Date'].min().date()
TODAY = MAX_DATE 

# 1. 本月第一天
CURRENT_MONTH_START = TODAY.replace(day=1)

# 2. 本周第一天 (周一)
CURRENT_WEEK_START = TODAY - datetime.timedelta(days=TODAY.weekday())
CURRENT_WEEK_DAYS = (TODAY - CURRENT_WEEK_START).days + 1

# 3. 上月日期范围
last_month_end = CURRENT_MONTH_START - datetime.timedelta(days=1)
last_month_start = last_month_end.replace(day=1)

# 4. 上周日期范围
last_week_start = CURRENT_WEEK_START - datetime.timedelta(days=7)
last_week_end = CURRENT_WEEK_START - datetime.timedelta(days=1)

# 5. 昨日
yesterday = TODAY - datetime.timedelta(days=1)
# ==============================================================================


# 初始化 Session State
if 'product_filters' not in st.session_state:
    all_notenames = df['BotNoteName'].dropna().unique().tolist()
    
    st.session_state.product_filters = {
        'date_option': '本月',
        'notename': [], 
        'start_date': CURRENT_MONTH_START, 
        'end_date': TODAY,
    }
    st.session_state.query_submitted = False
    
# --- 3. 页面配置与标题 ---
st.set_page_config(page_title="TG BOT数据看板", layout="wide")

# CSS 优化
st.markdown("""
<style>
.stMultiSelect div[data-testid="stMultiSelect"] > div > div:nth-child(2) div[data-baseweb="tag"] {
    background-color: #ADD8E6 !important;
    color: #000000 !important;
    border: 1px solid #ADD8E6 !important;
}
</style>
""", unsafe_allow_html=True)

# Request 1: 标题去掉文字 (30Min更新)
st.title("🚀 TG BOT数据看板")
st.markdown(f"**数据更新至：{str(TODAY)}**")

# --- 4. 核心数据指标 (Request 2, 3, 4, 5, 6) ---
st.header("📊 核心数据指标")

def get_data_in_range(df, start, end):
    """获取指定日期范围内的数据汇总"""
    mask = (df['Date'].dt.date >= start) & (df['Date'].dt.date <= end)
    subset = df[mask]
    total_consult = int(subset['Consultations'].sum())
    total_lead = int(subset['Leads'].sum())
    # 计算天数 (如果 start=end，也是1天)
    days = (end - start).days + 1
    days = days if days > 0 else 1
    return total_consult, total_lead, days

# --- 计算各周期数据 ---
tm_c, tm_l, tm_days = get_data_in_range(df, CURRENT_MONTH_START, TODAY)
lm_c, lm_l, lm_days = get_data_in_range(df, last_month_start, last_month_end)
tw_c, tw_l, _ = get_data_in_range(df, CURRENT_WEEK_START, TODAY)
lw_c, lw_l, _ = get_data_in_range(df, last_week_start, last_week_end)
t_c, t_l, _ = get_data_in_range(df, TODAY, TODAY)
y_c, y_l, _ = get_data_in_range(df, yesterday, yesterday)

# --- 1. 月度概览 (Request 2 & 3) ---
st.markdown("##### 📅 月度概览")

# 计算日均和差值
lm_avg_c = lm_c / lm_days
lm_avg_l = lm_l / lm_days
tm_avg_c = tm_c / tm_days
tm_avg_l = tm_l / tm_days

diff_c = tm_avg_c - lm_avg_c
diff_l = tm_avg_l - lm_avg_l

row1_1, row1_2, row1_3, row1_4 = st.columns(4)

# 上月：Request 2 - 前面不要有上箭头 (delta_color="off")
with row1_1:
    st.metric("上月总咨询数", f"{lm_c:,}", f"日均 {lm_avg_c:.1f}", delta_color="off")
with row1_2:
    st.metric("上月总线索数", f"{lm_l:,}", f"日均 {lm_avg_l:.1f}", delta_color="off")

# 本月：Request 3 - 绿色高/红色低，显示差值 (delta_color="normal" 会自动根据正负变色)
# 格式：日均 367.3 (差值 +50.0)
with row1_3:
    st.metric("本月总咨询数", f"{tm_c:,}", f"日均 {tm_avg_c:.1f} (差值 {diff_c:+.1f})", delta_color="normal")
with row1_4:
    st.metric("本月总线索数", f"{tm_l:,}", f"日均 {tm_avg_l:.1f} (差值 {diff_l:+.1f})", delta_color="normal")


# --- 2. 周度概览 (Request 4) ---
st.markdown("##### 🗓️ 周度概览 (周一到周日)") # Request 4: 标题修改

row2_1, row2_2, row2_3, row2_4 = st.columns(4)
with row2_1:
    st.metric("上周咨询数", f"{lw_c:,}") # Request 4: 去掉括号说明
with row2_2:
    st.metric("上周线索数", f"{lw_l:,}")
with row2_3:
    st.metric("本周咨询数", f"{tw_c:,}")
with row2_4:
    st.metric("本周线索数", f"{tw_l:,}")


# --- 3. 日度概览 (Request 5 & 6) ---
st.markdown("##### ⏰ 日度概览")

# 计算今日同比昨日变化
def calc_pct(curr, prev):
    if prev == 0:
        return 0.0 if curr == 0 else 100.0
    return (curr - prev) / prev * 100

pct_c = calc_pct(t_c, y_c)
pct_l = calc_pct(t_l, y_l)

row3_1, row3_2, row3_3, row3_4 = st.columns(4)

# 日期字符串
y_str = yesterday.strftime('%m-%d')
t_str = TODAY.strftime('%m-%d')

# Request 5: 昨日显示日期
with row3_1:
    st.metric(f"昨日咨询数 ({y_str})", f"{y_c:,}") 
with row3_2:
    st.metric(f"昨日线索数 ({y_str})", f"{y_l:,}")

# Request 6: 今日显示对比昨日百分比
with row3_3:
    st.metric(f"今日咨询数 ({t_str})", f"{t_c:,}", f"{pct_c:.1f}% vs 昨日", delta_color="normal")
with row3_4:
    st.metric(f"今日线索数 ({t_str})", f"{t_l:,}", f"{pct_l:.1f}% vs 昨日", delta_color="normal")

st.markdown("---")


# --- 5. 今日机器人数据柱状图 ---
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
    fig6.update_yaxes(range=[0, max_val * 1.1]) 
    
    st.plotly_chart(fig6, use_container_width=True)
else:
    st.info(f"今日 ({str(TODAY)}) 暂无机器人咨询数据。")

st.markdown("---")

# --- 6. 当月总趋势折线图 ---
st.header("📈 当月总趋势") 

df_month = df[df['Date'].dt.date >= CURRENT_MONTH_START].groupby('Date')[['Consultations', 'Leads']].sum().reset_index()

if not df_month.empty:
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
            
    fig7.update_xaxes(tickangle=45, type='category', dtick=1) 
    
    st.plotly_chart(fig7, use_container_width=True)
else:
    st.info("当月暂无数据。")

st.markdown("---")


# ====================================================================
# --- 7. 趋势分析筛选 ---
# ====================================================================

st.header("📊 趋势分析筛选")

@st.cache_data
def get_unique_list(df, col):
    return sorted(df[col].dropna().unique().tolist())

all_notenames = get_unique_list(df, 'BotNoteName')

with st.form("product_trend_form"):
    
    col1, col2 = st.columns(2)
    with col1:
        date_option = st.selectbox(
            "时间范围:",
            ("本月", "本周", "近7天", "近30天", "自定义日期"),
            key='form_date_option'
        )
    with col2:
        col_notename = st.multiselect("机器人备注名", all_notenames, default=st.session_state.product_filters['notename'], key='form_notename')
    
    start_date = MIN_DATE
    end_date = TODAY

    if date_option == "本月":
        start_date = CURRENT_MONTH_START
    elif date_option == "本周":
        start_date = CURRENT_WEEK_START
    elif date_option == "近7天":
        start_date = TODAY - datetime.timedelta(days=6)
    elif date_option == "近30天":
        start_date = TODAY - datetime.timedelta(days=29)
    elif date_option == "自定义日期":
        st.markdown("---")
        st.caption("自定义日期区间:")
        date_range_cols = st.columns(2)
        with date_range_cols[0]:
            start_date = st.date_input("起始日期", st.session_state.product_filters['start_date'], key='form_start_date', max_value=MAX_DATE, label_visibility="collapsed")
        with date_range_cols[1]:
            end_date = st.date_input("结束日期", st.session_state.product_filters['end_date'], key='form_end_date', max_value=MAX_DATE, label_visibility="collapsed")
            
    submitted = st.form_submit_button("🔍 查询趋势 / 更新数据源")


# --- 8. 执行筛选 ---
if submitted or not st.session_state.query_submitted:
    
    current_notenames = col_notename
    
    df_product_filtered_temp = df[
        (df['Date'].dt.date >= start_date) & 
        (df['Date'].dt.date <= end_date) &
        (df['BotNoteName'].isin(current_notenames))
    ].copy()
    
    st.session_state.df_product_filtered = df_product_filtered_temp
    st.session_state.query_submitted = True
    st.session_state.product_filters = {
        'date_option': date_option,
        'notename': current_notenames,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    if submitted:
        st.rerun()

df_product_filtered = st.session_state.df_product_filtered
current_product_filters = st.session_state.product_filters


# --- 9. 聚合趋势分析 ---

st.markdown("---")
st.subheader(f"📊 聚合趋势分析 (时间: {current_product_filters['start_date'].strftime('%m.%d')} - {current_product_filters['end_date'].strftime('%m.%d')})")

if not current_product_filters['notename']:
    st.warning("请在上方【机器人备注名】中选择至少一个机器人进行趋势分析。")
elif df_product_filtered.empty:
    st.info("当前筛选条件下没有找到任何数据。请调整筛选条件。")
else:
    df_trend_data = df_product_filtered.groupby('Date')[['Consultations', 'Leads']].sum().reset_index()
    df_trend_data['日期'] = df_trend_data['Date'].dt.strftime('%m.%d')
    df_trend_data = df_trend_data.rename(columns={'Consultations': '咨询', 'Leads': '线索'})

    current_notename_list = current_product_filters['notename']
    title_suffix = ""
    if len(current_notename_list) == len(all_notenames):
        title_suffix = " (所有机器人聚合)"
    elif len(current_notename_list) == 1:
        title_suffix = f" (机器人: {current_notename_list[0]})"
    else:
        title_suffix = f" (聚合 {len(current_notename_list)} 个机器人)"

    fig9 = px.line(df_trend_data, x='日期', y=['咨询', '线索'], 
                   labels={'value': '数量', 'variable': '指标'},
                   title="趋势分析" + title_suffix)
    
    for trace in fig9.data:
        if trace.name in ['咨询', '线索']:
            fig9.add_trace(go.Scatter(
                x=trace.x, y=trace.y, mode='text', 
                text=[f'{int(val)}' for val in trace.y], 
                textposition='top center', 
                name=trace.name + ' 标签', showlegend=False, marker=dict(size=0)
            ))
    
    fig9.update_xaxes(tickangle=45, type='category', dtick=1) 
    st.plotly_chart(fig9, use_container_width=True)


# --- 10. 查看源数据 ---
st.markdown("---")
notename_display = f"机器人: {len(current_product_filters['notename'])} 个"

with st.expander(f"查看源数据 (筛选区间: {current_product_filters['date_option']} / {notename_display})", expanded=False):
    st.dataframe(df_product_filtered.sort_values('Date', ascending=True), use_container_width=True)
