import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import gspread 

# --- 配置 ---
# 这里只需要 Key，不需要本地路径了
SPREADSHEET_KEY = '1WCiVbP4mR7v5MgDvEeNV8YCthkTVv0rBVv1DX5YkB1U' 

st.set_page_config(page_title="Bot 数据看板", layout="wide")
st.title("🤖 机器人数据预警看板 (实时自动更新)")
st.markdown(f"数据源：[点击查看 Google Sheets](https://docs.google.com/spreadsheets/d/{SPREADSHEET_KEY})")

@st.cache_data(ttl=3600)
def load_data():
    try:
        # 关键修改：只从 Streamlit Secrets 读取密钥
        # 这避免了所有文件路径错误
        if "gcp_service_account" not in st.secrets:
            st.error("未配置 Secrets！请在 Streamlit Cloud 后台配置 gcp_service_account。")
            st.stop()
            
        # 使用云端配置的字典直接连接
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)

        sh = gc.open_by_key(SPREADSHEET_KEY)
        worksheet = sh.sheet1 
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"❌ 数据加载失败: {e}")
        st.stop()
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("数据为空或读取失败")
    st.stop()

# --- 以下是原本的数据清洗和图表逻辑 (保持不变) ---
# 清理列名
df.columns = df.columns.astype(str).str.strip()

# 智能匹配列名
col_leads = None
col_consult = None
col_bot = None
col_group = None

for col in df.columns:
    if "线索" in col: col_leads = col
    if "咨询" in col and "率" not in col: col_consult = col
    if "机器人" in col: col_bot = col
    if "小组" in col: col_group = col

if not (col_leads and col_consult and col_bot):
    st.error(f"列名匹配失败。读取到的列: {list(df.columns)}")
    st.stop()

if not col_group:
    df['Group'] = 'Default'
    col_group = 'Group'

# 重命名
df = df.rename(columns={col_leads: 'Leads', col_consult: 'Consultations', col_bot: 'BotName', col_group: 'Group'})

# 处理日期 (强制取第一列)
first_col = df.columns[0]
df['Date'] = pd.to_datetime(df[first_col], errors='coerce')
df = df.dropna(subset=['Date']).sort_values('Date')

# 转换数字
df['Leads'] = pd.to_numeric(df['Leads'], errors='coerce').fillna(0)
df['Consultations'] = pd.to_numeric(df['Consultations'], errors='coerce').fillna(0)

# --- 侧边栏 ---
st.sidebar.header("筛选")
all_groups = list(df['Group'].unique())
selected_groups = st.sidebar.multiselect("选择小组", all_groups, default=all_groups)
df_filtered = df[df['Group'].isin(selected_groups)]

# --- 核心指标 ---
total_leads = df_filtered['Leads'].sum()
total_consults = df_filtered['Consultations'].sum()
st.metric("总线索数", int(total_leads))

# --- 图表 ---
st.subheader("📈 每日趋势")
bots = df_filtered['BotName'].unique()
target_bot = st.selectbox("选择机器人查看详情:", bots)

if target_bot:
    chart_data = df_filtered[df_filtered['BotName'] == target_bot]
    fig = px.line(chart_data, x='Date', y=['Leads', 'Consultations'], markers=True, title=f"{target_bot} 数据走势")
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("查看源数据"):
        st.dataframe(chart_data.sort_values('Date', ascending=False))