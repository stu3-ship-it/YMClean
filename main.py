import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import json

# --- 讀取 Secrets 設定 ---
GCP_INFO = dict(st.secrets["gcp_service_account"])
CONFIG = st.secrets["system_config"]

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# --- 功能函式 ---

def check_connections():
    """診斷系統連線狀態"""
    status = {"GCP憑證": False, "Google Sheets": False, "Google Drive": False}
    
    try:
        # 1. GCP 憑證讀取
        creds = Credentials.from_service_account_info(GCP_INFO, scopes=SCOPE)
        status["GCP憑證"] = True
        
        # 2. Google Sheets 連線
        client = gspread.authorize(creds)
        client.open_by_key(CONFIG["sheet_id"])
        status["Google Sheets"] = True
        
        # 3. Google Drive 連線
        service = build('drive', 'v3', credentials=creds)
        service.files().get(fileId=CONFIG["folder_id"]).execute()
        status["Google Drive"] = True
    except Exception as e:
        # 可視需求在開發階段 print(e) 除錯
        pass
        
    return status

@st.cache_data(ttl=600)
def fetch_student_data():
    """從 Google Sheets 獲取學生清單"""
    try:
        creds = Credentials.from_service_account_info(GCP_INFO, scopes=SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(CONFIG["sheet_id"]).sheet1
        return sheet.get_all_records()
    except:
        return []

# --- 側邊欄 (Sidebar) ---

with st.sidebar:
    st.title("🛡️ 系統選單")
    
    # 單選按鈕選單 (放在診斷上方)
    menu_options = ["衛生糾察", "班級察看", "系統管理"]
    choice = st.radio("功能切換", menu_options)
    
    st.divider()
    
    # 系統連線診斷
    st.subheader("🔍 系統連線診斷")
    diag = check_connections()
    for key, val in diag.items():
        if val:
            st.success(f"● {key}: 正常")
        else:
            st.error(f"● {key}: 異常")

# --- 主頁面內容 ---

st.title(f"🚀 {choice}系統")

if choice == "衛生糾察":
    pwd = st.text_input("請輸入衛生糾察通行碼", type="password")
    if pwd == CONFIG["team_password"]:
        st.success("身分驗證成功")
        st.divider()
        
        raw_data = fetch_student_data()
        if raw_data:
            # 第一層：年級
            grades = sorted(list(set(str(d.get('年級', '未知')) for d in raw_data)))
            selected_grade = st.selectbox("請選擇年級", grades)
            
            # 第二層：學號與姓名
            filtered_students = [d for d in raw_data if str(d.get('年級')) == selected_grade]
            student_options = [f"{d.get('學號')} - {d.get('姓名')}" for d in filtered_students]
            selected_student = st.selectbox("請選擇學生 (學號 - 姓名)", student_options)
            
            st.info(f"📋 已選取：{selected_student}")
        else:
            st.warning("目前無法讀取學生資料，請檢查 Google Sheets 內容與權限。")
            
    elif pwd != "":
        st.error("❌ 通行碼錯誤")

elif choice == "班級察看":
    st.info("此頁面顯示各班級統計資訊 (開發中)")
    # 這裡可以直接呈現 Google Sheets 的摘要數據

elif choice == "系統管理":
    pwd = st.text_input("請輸入系統管理通行碼", type="password")
    if pwd == CONFIG["admin_password"]:
        st.success("管理員模式已開啟")
        st.write("---")
        st.write("🔧 系統參數設定")
        st.json(dict(CONFIG)) # 僅供展示
    elif pwd != "":
        st.error("❌ 通行碼錯誤")
