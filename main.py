import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# --- 網頁初始設定 ---
st.set_page_config(page_title="校園環境評分系統", layout="wide")

# --- 讀取 Secrets 設定 ---
GCP_INFO = dict(st.secrets["gcp_service_account"])
CONFIG = st.secrets["system_config"]

SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# --- 初始化 Session State ---
if 'auth_team' not in st.session_state: st.session_state.auth_team = False
if 'auth_admin' not in st.session_state: st.session_state.auth_admin = False

# --- Google Sheets 功能函式 ---

def get_gspread_client():
    creds = Credentials.from_service_account_info(GCP_INFO, scopes=SCOPE)
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def fetch_sheet_data(worksheet_name):
    """通用抓取頁籤資料函式"""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet(worksheet_name)
        return sheet.get_all_records()
    except: return []

def get_setting_date(key_name):
    """取得 settings 頁籤中的日期設定"""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("settings")
        cell = sheet.find(key_name)
        val = sheet.cell(cell.row, cell.col + 1).value
        return datetime.strptime(val, '%Y-%m-%d').date()
    except: return datetime.now().date()

def calculate_school_week(target_date, start_date):
    """計算週次：開學日當週為第一週，過週日後為下一週"""
    # 找出開學日當週的週一
    start_monday = start_date - timedelta(days=start_date.weekday())
    # 找出目標日當週的週一
    target_monday = target_date - timedelta(days=target_date.weekday())
    # 計算差距週數
    week_diff = (target_monday - start_monday).days // 7
    return week_diff + 1

# --- 側邊欄 ---
with st.sidebar:
    st.title("🛡️ 系統選單")
    choice = st.radio("請選擇模式", ["衛生糾察", "班級察看", "系統管理"])
    st.divider()
    # (連線診斷略，保留原功能)

# --- 主頁面 ---
st.title("校園環境評分系統")

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
        # --- 登入後介面 ---
        
        # A. 評分人員選擇區
        inspectors_data = fetch_sheet_data("inspectors")
        if inspectors_data:
            grade_map = {"一年級": "1", "二年級": "2", "三年級": "3"}
            # 刪除年級下的分隔線 (直接並列)
            sel_grade = st.radio("請選擇年級", list(grade_map.keys()), horizontal=True)
            
            prefix = grade_map[sel_grade]
            names = sorted([r['姓名'] for r in inspectors_data if str(r.get('班級', '')).startswith(prefix)])
            
            if names:
                selected_name = st.radio("請選擇您的姓名", names, horizontal=True)
                st.info(f"👤 當前評分員：{selected_name}")
            
            # 在顯示評分員下方增加分隔線
            st.divider()
        
        # B. 檢查日期與週次
        col1, col2 = st.columns([1, 1])
        with col1:
            inspect_date = st.date_input("檢查日期", datetime.now().date())
        with col2:
            start_date = get_setting_date("semester_start")
            current_week = calculate_school_week(inspect_date, start_date)
            st.metric("當前週次", f"第 {current_week} 週")
            
        st.write("---")

        # C. 受檢班級選擇區
        st.subheader("📍 選擇受檢班級")
        roster_data = fetch_sheet_data("roster")
        
        if roster_data:
            # 第一階層：年級
            target_grade_label = st.radio("受檢年級", ["一年級", "二年級", "三年級"], horizontal=True, key="target_grade")
            target_prefix = grade_map[target_grade_label]
            
            # 第二階層：班級 (過濾 1, 2, 3 開頭)
            # 假設 roster 頁籤欄位名稱為 "班級"
            target_classes = sorted(list(set([
                str(r['班級']) for r in roster_data 
                if str(r.get('班級', '')).startswith(target_prefix)
            ])))
            
            if target_classes:
                selected_class = st.radio("受檢班級", target_classes, horizontal=True)
                st.success(f"📋 已選擇受檢班級：{selected_class}")
            else:
                st.warning("查無對應班級資料")
        else:
            st.error("無法讀取 roster 頁籤資料")

# --- 2. 班級察看 (略) ---

# --- 3. 系統管理頁面 ---
elif choice == "系統管理":
    if not st.session_state.auth_admin:
        pwd = st.text_input("請輸入系統管理通行碼", type="password")
        if st.button("管理員登入"):
            if pwd == CONFIG["admin_password"]:
                st.session_state.auth_admin = True
                st.rerun()
    else:
        tabs = st.tabs(["進度監控", "成績總表", "扣分明細", "寄送通知", "申訴審核", "系統設定", "名單更新"])
        
        with tabs[5]: # 系統設定
            st.subheader("⚙️ 系統參數設定")
            # 讀取現有開學日
            try:
                current_start = get_setting_date("semester_start")
                new_start = st.date_input("開學日 (semester_start)", current_start)
                
                if st.button("更新開學日"):
                    client = get_gspread_client()
                    sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("settings")
                    cell = sheet.find("semester_start")
                    sheet.update_cell(cell.row, cell.col + 1, str(new_start))
                    st.success(f"已更新開學日為: {new_start}")
                    st.cache_data.clear()
            except:
                st.error("請確認 settings 頁籤包含 semester_start 欄位")
