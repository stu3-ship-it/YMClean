import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime

# --- 網頁初始設定 ---
st.set_page_config(page_title="校園環境評分系統", layout="wide")

# --- 讀取 Secrets 設定 ---
GCP_INFO = dict(st.secrets["gcp_service_account"])
CONFIG = st.secrets["system_config"]

SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# --- 初始化 Session State ---
if 'auth_team' not in st.session_state: st.session_state.auth_team = False
if 'auth_admin' not in st.session_state: st.session_state.auth_admin = False

# --- Google Sheets 共用函式 ---

def get_gspread_client():
    creds = Credentials.from_service_account_info(GCP_INFO, scopes=SCOPE)
    return gspread.authorize(creds)

def check_connections():
    status = {"GCP憑證": False, "Google Sheets": False, "Google Drive": False}
    try:
        creds = Credentials.from_service_account_info(GCP_INFO, scopes=SCOPE)
        status["GCP憑證"] = True
        client = gspread.authorize(creds)
        client.open_by_key(CONFIG["sheet_id"])
        status["Google Sheets"] = True
        service = build('drive', 'v3', credentials=creds)
        service.files().get(fileId=CONFIG["folder_id"]).execute()
        status["Google Drive"] = True
    except: pass
    return status

@st.cache_data(ttl=60)
def fetch_inspectors():
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("inspectors")
        return sheet.get_all_records()
    except: return []

def get_setting_date(key_name):
    """取得 settings 頁籤中的日期"""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("settings")
        # 假設 A 欄是 Key, B 欄是 Value
        cell = sheet.find(key_name)
        val = sheet.cell(cell.row, cell.col + 1).value
        return datetime.strptime(val, '%Y-%m-%d').date()
    except: return datetime.now().date()

def update_setting_date(key_name, new_date):
    """更新 settings 頁籤中的日期"""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("settings")
        cell = sheet.find(key_name)
        sheet.update_cell(cell.row, cell.col + 1, str(new_date))
        return True
    except: return False

# --- 側邊欄 ---
with st.sidebar:
    st.title("🛡️ 系統選單")
    choice = st.radio("請選擇模式", ["衛生糾察", "班級察看", "系統管理"])
    st.divider()
    st.subheader("🔍 系統連線診斷")
    diag = check_connections()
    for key, val in diag.items():
        if val: st.success(f"● {key}: 正常")
        else: st.error(f"● {key}: 異常")

# --- 主頁面 ---
st.title(f"校園環境評分系統")

# --- 1. 衛生糾察 ---
if choice == "衛生糾察":
    if not st.session_state.auth_team:
        pwd = st.text_input("請輸入衛生糾察通行碼", type="password")
        if st.button("登入"):
            if pwd == CONFIG["team_password"]:
                st.session_state.auth_team = True
                st.rerun()
            else: st.error("❌ 通行碼錯誤")
    else:
        # 登入後介面
        data = fetch_inspectors()
        if data:
            grade_map = {"一年級": "1", "二年級": "2", "三年級": "3"}
            selected_grade = st.radio("請選擇年級", list(grade_map.keys()), horizontal=True)
            
            # 過濾與排序
            prefix = grade_map[selected_grade]
            names = sorted([r['姓名'] for r in data if str(r.get('班級', '')).startswith(prefix)])
            
            if names:
                st.write("---")
                selected_name = st.radio("請選擇您的姓名", names, horizontal=True)
                st.info(f"📍 評分員：{selected_name}")
            else:
                st.warning("查無該年級名單")

# --- 2. 班級察看 ---
elif choice == "班級察看":
    st.subheader("📊 各班評分進度與成績")
    st.info("此模組可串接成績總表數據。")

# --- 3. 系統管理 ---
elif choice == "系統管理":
    if not st.session_state.auth_admin:
        pwd = st.text_input("請輸入系統管理通行碼", type="password")
        if st.button("管理員登入"):
            if pwd == CONFIG["admin_password"]:
                st.session_state.auth_admin = True
                st.rerun()
            else: st.error("❌ 密碼錯誤")
    else:
        # 登入後的分頁系統
        tabs = st.tabs(["進度監控", "成績總表", "扣分明細", "寄送通知", "申訴審核", "系統設定", "名單更新"])
        
        with tabs[0]: st.write("🎥 顯示今日各區評分完成率")
        with tabs[1]: st.write("🏆 班級排行總表")
        with tabs[2]: st.write("📝 違規細項查詢")
        with tabs[3]: st.write("📧 寄送扣分通知信")
        with tabs[4]: st.write("⚖️ 處理班級申訴案件")
        
        with tabs[5]: # 系統設定
            st.subheader("⚙️ 系統參數設定")
            current_start_date = get_setting_date("semester_start")
            new_date = st.date_input("開學日 (semester_start)", current_start_date)
            
            if st.button("更新開學日"):
                if update_setting_date("semester_start", new_date):
                    st.success("✅ 開學日已更新至 Google 表單")
                    st.cache_data.clear() # 清除快取以確保數據最新
                else:
                    st.error("❌ 更新失敗，請檢查 settings 頁籤格式")
                    
        with tabs[6]: st.write("🔄 從 Google Sheets 同步人員與班級清單")
