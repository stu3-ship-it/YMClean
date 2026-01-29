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
    menu_options = ["衛生糾察", "班級察看
