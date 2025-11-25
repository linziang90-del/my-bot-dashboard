import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import gspread 

# --- 配置 ---
SPREADSHEET_KEY = '1WCiVbP4mR7v5MgDvEeNV8YCthkTVv0rBVv1DX5YkB1U' 

# 缓存时间 30分钟
@st.cache_data(ttl=3600) 
def load_data():
    """连接 Google Sheets 并加载数据 (高性能版)"""
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("未配置 Secrets！请在 Streamlit Cloud 后台配置 gcp_service_account。")
            st.stop()
            
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)

        sh = gc.open_by_key(SPREADSHEET_KEY)
        worksheet = sh.sheet1 
        
        # ⚡️ 性能优化：改用 get_all_values()
        raw_data = worksheet.get_all_values()
        
        if not raw_data:
            return pd.DataFrame()
            
        headers = raw_data[0]
        rows = raw_data[1:]
        
        df = pd.DataFrame(rows, columns=headers)
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
    st.title("🚀 TG BOT数据看板")
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

CURRENT_MONTH_START = TODAY.replace(day=1)
CURRENT_WEEK_START = TODAY - datetime.timedelta(days=TODAY.weekday())

last_month_end = CURRENT_MONTH_START - datetime.timedelta(days=1)
last_month_start = last_month_end.replace(day=1)

last_week_start = CURRENT_WEEK_START - datetime.timedelta(days=7)
last_week_end = CURRENT_WEEK_START - datetime.timedelta(days=1)

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

st.markdown("""
<style>
.stMultiSelect div[data-testid="stMultiSelect"] > div > div:nth-child(2) div[data-baseweb="tag"] {
    background-color: #ADD8E6 !important;
    color: #000000 !important;
    border: 1px solid #ADD8E6 !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🚀 TG BOT数据看板")
st.markdown(f"**数据更新至：{str(TODAY)}**")

# --- 4. 核心数据指标 (总览) ---
st.header("📊 核心数据指标 (总览)")

def get_data_in_range(df, start, end):
    """获取指定日期范围内的数据汇总"""
    mask = (df['Date'].dt.date >= start) & (df['Date'].dt.date <= end)
    subset = df[mask]
    total_consult = int(subset['Consultations'].sum())
    total_lead = int(subset['Leads'].sum())
    days = (end - start).days + 1
    days = days if days > 0 else 1
    return total_consult, total_lead, days

tm_c, tm_l, tm_days = get_data_in_range(df, CURRENT_MONTH_START, TODAY)
lm_c, lm_l, lm_days = get_data_in_range(df, last_month_start, last_month_end)
tw_c, tw_l, _ = get_data_in_range(df, CURRENT_WEEK_START, TODAY)
lw_c, lw_l, _ = get_data_in_range(df, last_week_start, last_week_end)
t_c, t_l, _ = get_data_in_range(df, TODAY, TODAY)
y_c, y_l, _ = get_data_in_range(df, yesterday, yesterday)

# 略去核心指标展示代码... (保持 V13 逻辑)
lm_avg_c = lm_c / lm_days
lm_avg_l = lm_l / lm_days
tm_avg_c = tm_c / tm_days
tm_avg_l = tm_l / tm_days
diff_c = tm_avg_c - lm_avg_c
diff_l = tm_avg_l - lm_avg_l
pct_c = 0.0 if y_c == 0 else (t_c - y_c) / y_c * 100
pct_l = 0.0 if y_l == 0 else (t_l - y_l) / y_l * 100
y_str = yesterday.strftime('%m-%d')
t_str = TODAY.strftime('%m-%d')

st.markdown("##### 📅 月度概览")
row1_1, row1_2, row1_3, row1_4 = st.columns(4)
with row1_1: st.metric("上月总咨询数", f"{lm_c:,}", f"日均 {lm_avg_c:.1f}", delta_color="off")
with row1_2: st.metric("上月总线索数", f"{lm_l:,}", f"日均 {lm_avg_l:.1f}", delta_color="off")
with row1_3: st.metric("本月总咨询数", f"{tm_c:,}", f"日均 {tm_avg_c:.1f} (差值 {diff_c:+.1f})", delta_color="normal")
with row1_4: st.metric("本月总线索数", f"{tm_l:,}", f"日均 {tm_avg_l:.1f} (差值 {diff_l:+.1f})", delta_color="normal")

st.markdown("##### 🗓️ 周度概览 (周一到周日)")
row2_1, row2_2, row2_3, row2_4 = st.columns(4)
with row2_1: st.metric("上周咨询数", f"{lw_c:,}")
with row2_2: st.metric("上周线索数", f"{lw_l:,}")
with row2_3: st.metric("本周咨询数", f"{tw_c:,}")
with row2_4: st.metric("本周线索数", f"{tw_l:,}")

st.markdown("##### ⏰ 日度概览")
row3_1, row3_2, row3_3, row3_4 = st.columns(4)
with row3_1: st.metric(f"昨日咨询数 ({y_str})", f"{y_c:,}")
with row3_2: st.metric(f"昨日线索数 ({y_str})", f"{y_l:,}")
with row3_3: st.metric(f"今日咨询数 ({t_str})", f"{t_c:,}", f"{pct_c:.1f}% vs 昨日", delta_color="normal")
with row3_4: st.metric(f"今日线索数 ({t_str})", f"{t_l:,}", f"{pct_l:.1f}% vs 昨日", delta_color="normal")

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
    
    try:
        st.plotly_chart(fig6, use_container_width=True)
    except:
        st.plotly_chart(fig6, width='stretch')
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
    
    try:
        st.plotly_chart(fig7, use_container_width=True)
    except:
        st.plotly_chart(fig7, width='stretch')
else:
    st.info("当月暂无数据。")

st.markdown("---")

# ====================================================================
# 🔥🔥🔥 NEW SECTION 7: 各小组核心数据指标
# ====================================================================
st.header("🏢 各小组核心数据指标")

REQUIRED_GROUPS = [
    '项目一组', '项目二组', '项目三组', '项目四组', 
    '投放一组', '投放二组', '投放三组'
]

# --- 预先计算 Bot 周度对比数据 ---
df_week = df[df['Date'].dt.date >= last_week_start].copy()
df_cw = df_week[df_week['Date'].dt.date >= CURRENT_WEEK_START]
df_lw = df_week[df_week['Date'].dt.date <= last_week_end]

# 聚合本周和上周的咨询数 (按组和 Bot)
df_cw_agg = df_cw.groupby(['Group', 'BotNoteName'])['Consultations'].sum().reset_index(name='CW_Consultations')
df_lw_agg = df_lw.groupby(['Group', 'BotNoteName'])['Consultations'].sum().reset_index(name='LW_Consultations')

# 合并并计算涨跌
df_compare = pd.merge(df_cw_agg, df_lw_agg, on=['Group', 'BotNoteName'], how='outer').fillna(0)
df_compare['Diff'] = df_compare['CW_Consultations'] - df_compare['LW_Consultations']

def calculate_pct_change(row):
    if row['LW_Consultations'] == 0:
        return 100.0 if row['CW_Consultations'] > 0 else 0.0
    return (row['CW_Consultations'] - row['LW_Consultations']) / row['LW_Consultations'] * 100
    
df_compare['Pct_Change'] = df_compare.apply(calculate_pct_change, axis=1)
# -----------------------------------


present_groups = df['Group'].dropna().unique()
groups_to_render = [g for g in REQUIRED_GROUPS if g in present_groups]

if not groups_to_render:
    st.info("当前数据集中未找到指定小组数据。")

for group_name in groups_to_render:
    # 过滤出当前组的数据
    df_group_standard = df[df['Group'] == group_name]
    df_group_compare = df_compare[df_compare['Group'] == group_name]

    with st.expander(f"✅ **{group_name}** 核心表现 (点击展开)", expanded=False):
        
        # --- 1. 标准核心指标计算 ---
        tm_c, tm_l, tm_days = get_data_in_range(df_group_standard, CURRENT_MONTH_START, TODAY)
        tw_c, tw_l, _ = get_data_in_range(df_group_standard, CURRENT_WEEK_START, TODAY)
        t_c, t_l, _ = get_data_in_range(df_group_standard, TODAY, TODAY)
        
        # 布局：月度、周度、日度
        col_m_c, col_m_l, col_w_c, col_w_l, col_d_c, col_d_l = st.columns(6)

        with col_m_c: st.metric("本月总咨询", f"{tm_c:,}")
        with col_m_l: st.metric("本月总线索", f"{tm_l:,}")
        with col_w_c: st.metric("本周咨询", f"{tw_c:,}")
        with col_w_l: st.metric("本周线索", f"{tw_l:,}")
        with col_d_c: st.metric("今日咨询", f"{t_c:,}")
        with col_d_l: st.metric("今日线索", f"{t_l:,}")

        st.markdown("---")
        st.markdown("##### 📈 本周咨询涨跌排名 (Bot)")

        # --- 2. 查找涨跌幅最大的 Bot ---
        
        # 查找下降最多 (最低百分比)
        max_down_row = df_group_compare[df_group_compare['Pct_Change'] < 0].sort_values(by='Pct_Change', ascending=True).head(1)
        
        # 查找上升最多 (最高百分比)
        # 确保 CW_Consultations > LW_Consultations 或 Pct_Change > 0 (后者已在筛选中)
        max_up_row = df_group_compare[df_group_compare['Pct_Change'] > 0].sort_values(by='Pct_Change', ascending=False).head(1)
        
        col_down, col_up = st.columns(2)

        # 展示下降最多的 Bot
        with col_down:
            if not max_down_row.empty:
                down_data = max_down_row.iloc[0]
                # Pct_Change 已经是负数
                delta_val = f"{down_data['Pct_Change']:.1f}% ({down_data['Diff']:.0f}次)"
                st.metric(
                    label="🔻 下降最多 Bot (本周 vs 上周)", 
                    value=f"Bot: {down_data['BotNoteName']}", 
                    delta=delta_val, 
                    delta_color="inverse" # 负数显示红色
                )
            else:
                st.info("本周无咨询下降的 Bot")
        
        # 展示上升最多的 Bot
        with col_up:
            if not max_up_row.empty:
                up_data = max_up_row.iloc[0]
                # Pct_Change 是正数，Diff 是正数
                delta_val = f"+{up_data['Pct_Change']:.1f}% (+{up_data['Diff']:.0f}次)"
                st.metric(
                    label="⬆️ 上升最多 Bot (本周 vs 上周)", 
                    value=f"Bot: {up_data['BotNoteName']}", 
                    delta=delta_val, 
                    delta_color="normal" # 正数显示绿色
                )
            else:
                st.info("本周无咨询上升的 Bot")

st.markdown("---")


# ====================================================================
# --- NEW SECTION 8: 趋势分析筛选 (原 Section 7) ---
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


# --- 9. 执行筛选 ---
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


# --- 10. 聚合趋势分析 ---

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
    
    try:
        st.plotly_chart(fig9, use_container_width=True)
    except:
        st.plotly_chart(fig9, width='stretch')


# --- 11. 查看源数据 ---
st.markdown("---")
notename_display = f"机器人: {len(current_product_filters['notename'])} 个"

with st.expander(f"查看源数据 (筛选区间: {current_product_filters['date_option']} / {notename_display})", expanded=False):
    try:
        st.dataframe(df_product_filtered.sort_values('Date', ascending=True), use_container_width=True)
    except:
        st.dataframe(df_product_filtered.sort_values('Date', ascending=True), width='stretch')
