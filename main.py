import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# --- 網頁初始設定 ---
st.set_page_config(page_title="校園環境評分系統", layout="wide")

# --- 讀取 Secrets 設定 ---
# 確保 GitHub Secrets 中已設定 gcp_service_account 與 system_config
GCP_INFO = dict(st.secrets["gcp_service_account"])
CONFIG = st.secrets["system_config"]

SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# --- 初始化 Session State ---
if 'auth_team' not in st.session_state: st.session_state.auth_team = False
if 'auth_admin' not in st.session_state: st.session_state.auth_admin = False

# --- 核心功能函式 ---

def get_gspread_client():
    creds = Credentials.from_service_account_info(GCP_INFO, scopes=SCOPE)
    return gspread.authorize(creds)

def get_connection_status():
    """診斷系統連線狀態，回傳布林值字典"""
    status = {"GCP憑證": False, "Google Sheets": False, "Google Drive": False}
    try:
        # 1. GCP 憑證讀取狀態
        creds = Credentials.from_service_account_info(GCP_INFO, scopes=SCOPE)
        status["GCP憑證"] = True
        
        # 2. Google Sheets 連線狀態
        client = gspread.authorize(creds)
        client.open_by_key(CONFIG["sheet_id"])
        status["Google Sheets"] = True
        
        # 3. Google Drive 資料夾連線狀態
        service = build('drive', 'v3', credentials=creds)
        service.files().get(fileId=CONFIG["folder_id"]).execute()
        status["Google Drive"] = True
    except:
        pass
    return status

@st.cache_data(ttl=60)
def fetch_sheet_data(worksheet_name):
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet(worksheet_name)
        return sheet.get_all_records()
    except: return []

def calculate_school_week(target_date, start_date):
    start_monday = start_date - timedelta(days=start_date.weekday())
    target_monday = target_date - timedelta(days=target_date.weekday())
    week_diff = (target_monday - start_monday).days // 7
    return week_diff + 1

# --- 側邊欄 (Sidebar) ---
with st.sidebar:
    st.title("🛡️ 系統選單")
    
    # 1. 選擇模式
    choice = st.radio("請選擇模式", ["衛生糾察", "班級察看", "系統管理"])
    
    # 2. 分隔線
    st.divider()
    
    # 3. 系統連線診斷
    st.subheader("🔍 系統連線診斷")
    diag = get_connection_status()
    
    # 使用 columns 或直接條列顯示狀態
    col_status = st.container()
    with col_status:
        st.write(f"{'🟢' if diag['GCP憑證'] else '🔴'} GCP憑證讀取狀態")
        st.write(f"{'🟢' if diag['Google Sheets'] else '🔴'} Google Sheets連線狀態")
        st.write(f"{'🟢' if diag['Google Drive'] else '🔴'} Google Drive資料夾連線")

# --- 主頁面：標題 ---
st.header("🏫 校園環境評分系統")

# --- 1. 衛生糾察頁面 ---
if choice == "衛生糾察":
    if not st.session_state.auth_team:
        pwd = st.text_input("請輸入衛生糾察通行碼", type="password")
        if st.button("登入"):
            if pwd == CONFIG["team_password"]:
                st.session_state.auth_team = True
                st.rerun()
            else: st.error("❌ 通行碼錯誤")
    else:
        # 進入後的操作頁面
        # A. 評分人員選擇
        inspectors_data = fetch_sheet_data("inspectors")
        if inspectors_data:
            grade_map = {"一年級": "1", "二年級": "2", "三年級": "3"}
            sel_grade = st.radio("請選擇年級", list(grade_map.keys()), horizontal=True)
            
            prefix = grade_map[sel_grade]
            names = sorted([r['姓名'] for r in inspectors_data if str(r.get('班級', '')).startswith(prefix)])
            
            if names:
                selected_name = st.radio("請選擇您的姓名", names, horizontal=True)
                st.info(f"👤 當前評分員：{selected_name}")
                st.divider() # 在顯示評分員下方增加分隔線
        
        # B. 檢查日期與週次
        col1, col2 = st.columns(2)
        with col1:
            inspect_date = st.date_input("檢查日期", datetime.now().date())
        with col2:
            # 取得開學日並計算週次
            try:
                client = get_gspread_client()
                s_sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("settings")
                s_val = s_sheet.cell(s_sheet.find("semester_start").row, s_sheet.find("semester_start").col + 1).value
                start_date = datetime.strptime(s_val, '%Y-%m-%d').date()
                current_week = calculate_school_week(inspect_date, start_date)
                st.metric("當前週次", f"第 {current_week} 週")
            except:
                st.warning("無法計算週次，請檢查設定頁籤。")

        # C. 受檢班級選擇
        st.write("---")
        st.subheader("📍 選擇受檢班級")
        roster_data = fetch_sheet_data("roster")
        if roster_data:
            target_grade_label = st.radio("受檢年級", ["一年級", "二年級", "三年級"], horizontal=True, key="tg")
            tg_prefix = {"一年級": "1", "二年級": "2", "三年級": "3"}[target_grade_label]
            
            target_classes = sorted(list(set([
                str(r['班級']) for r in roster_data 
                if str(r.get('班級', '')).startswith(tg_prefix)
            ])))
            
            if target_classes:
                selected_class = st.radio("受檢班級", target_classes, horizontal=True)
            else:
                st.warning("該年級無班級資料")

# --- 3. 系統管理頁面 ---
elif choice == "系統管理":
    if not st.session_state.auth_admin:
        pwd = st.text_input("請輸入系統管理通行碼", type="password")
        if st.button("管理員登入"):
            if pwd == CONFIG["admin_password"]:
                st.session_state.auth_admin = True
                st.rerun()
    else:
        # 管理頁籤
        tabs = st.tabs(["進度監控", "成績總表", "扣分明細", "寄送通知", "申訴審核", "系統設定", "名單更新"])
        
        with tabs[5]: # 系統設定
            st.subheader("⚙️ 系統參數設定")
            try:
                client = get_gspread_client()
                sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("settings")
                cell = sheet.find("semester_start")
                current_val = sheet.cell(cell.row, cell.col + 1).value
                
                new_start = st.date_input("開學日 (semester_start)", datetime.strptime(current_val, '%Y-%m-%d').date())
                if st.button("更新開學日"):
                    sheet.update_cell(cell.row, cell.col + 1, str(new_start))
                    st.success("✅ 更新成功")
                    st.cache_data.clear()
            except:
                st.error("設定讀取失敗")
