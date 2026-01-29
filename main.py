import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# --- 網頁初始設定 ---
st.set_page_config(page_title="校園環境評分系統", layout="centered")

# --- 讀取 Secrets 設定 ---
GCP_INFO = dict(st.secrets["gcp_service_account"])
CONFIG = st.secrets["system_config"]

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# --- 初始化 Session State (用於記錄登入狀態) ---
if 'auth_team' not in st.session_state:
    st.session_state.auth_team = False
if 'auth_admin' not in st.session_state:
    st.session_state.auth_admin = False

# --- 功能函式 ---

def check_connections():
    """診斷系統連線狀態"""
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
    except:
        pass
    return status

@st.cache_data(ttl=300)
def fetch_inspectors_data():
    """從 Google Sheets 的 'inspectors' 頁籤獲取資料"""
    try:
        creds = Credentials.from_service_account_info(GCP_INFO, scopes=SCOPE)
        client = gspread.authorize(creds)
        # 指定讀取 inspectors 頁籤
        sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("inspectors")
        return sheet.get_all_records()
    except Exception as e:
        st.error(f"資料抓取失敗: {e}")
        return []

# --- 側邊欄 (Sidebar) ---

with st.sidebar:
    st.title("🛡️ 系統選單")
    
    # 1. 請選擇模式 (單選按鈕)
    menu_options = ["衛生糾察", "班級察看", "系統管理"]
    choice = st.radio("請選擇模式", menu_options)
    
    st.divider()
    
    # 2. 系統連線診斷
    st.subheader("🔍 系統連線診斷")
    diag = check_connections()
    for key, val in diag.items():
        if val:
            st.success(f"● {key}: 正常")
        else:
            st.error(f"● {key}: 異常")

# --- 主頁面內容 ---

st.header(f"校園環境評分系統 - {choice}")

# --- A. 衛生糾察頁面 ---
if choice == "衛生糾察":
    if not st.session_state.auth_team:
        # 登入介面
        pwd = st.text_input("請輸入衛生糾察通行碼", type="password")
        if st.button("登入"):
            if pwd == CONFIG["team_password"]:
                st.session_state.auth_team = True
                st.rerun() # 重新整理以隱藏登入框
            else:
                st.error("❌ 通行碼錯誤")
    else:
        # 登入成功後的操作頁面
        st.success("✅ 已進入衛生糾察模式")
        if st.button("登出"):
            st.session_state.auth_team = False
            st.rerun()
            
        st.divider()
        
        # 取得資料
        data = fetch_inspectors_data()
        
        if data:
            # 第一層：年級 (單選按鈕)
            grade_map = {"一年級": "1", "二年級": "2", "三年級": "3"}
            selected_grade_label = st.radio("請選擇年級", list(grade_map.keys()), horizontal=True)
            grade_prefix = grade_map[selected_grade_label]
            
            # 第二層：姓名過濾與排序
            # 邏輯：檢查「班級」欄位是否以該年級數字開頭
            filtered_names = [
                row['姓名'] for row in data 
                if str(row.get('班級', '')).startswith(grade_prefix)
            ]
            filtered_names.sort() # 由小到大排序
            
            if filtered_names:
                selected_inspector = st.radio("請選擇您的姓名", filtered_names)
                st.info(f"📍 當前評分人員：{selected_inspector}")
            else:
                st.warning(f"⚠️ 找不到{selected_grade_label}的相關資料")
        else:
            st.error("無法讀取 inspectors 頁籤資料，請確認工作表名稱。")

# --- B. 班級察看頁面 ---
elif choice == "班級察看":
    st.info("📊 這裡將顯示各班級的評分統計結果。")
    # 此處可加入圖表或表格呈現

# --- C. 系統管理頁面 ---
elif choice == "系統管理":
    if not st.session_state.auth_admin:
        # 登入介面
        pwd = st.text_input("請輸入系統管理通行碼", type="password")
        if st.button("管理員登入"):
            if pwd == CONFIG["admin_password"]:
                st.session_state.auth_admin = True
                st.rerun()
            else:
                st.error("❌ 管理密碼錯誤")
    else:
        # 登入成功後的管理頁面
        st.success("🔑 管理員權限已啟動")
        if st.button("登出系統管理"):
            st.session_state.auth_admin = False
            st.rerun()
        
        st.divider()
        st.write("⚙️ 系統組態資訊")
        st.json({
            "Sheet ID": CONFIG["sheet_id"],
            "Folder ID": CONFIG["folder_id"],
            "GCP Project": GCP_INFO["project_id"]
        })
