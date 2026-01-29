import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# --- 初始設定 ---
# 假設的通行碼（實際建議存在環境變數）
PASSCODES = {
    "衛生糾察": "hc123",
    "系統管理": "admin888"
}

# Google API 範圍
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# --- 功能函式 ---

def check_connections(json_path, spreadsheet_id, folder_id):
    """診斷系統連線狀態"""
    status = {"GCP憑證": False, "Google Sheets": False, "Google Drive": False}
    
    # 1. GCP 憑證讀取
    try:
        creds = Credentials.from_service_account_file(json_path, scopes=SCOPE)
        status["GCP憑證"] = True
    except Exception:
        return status

    # 2. Google Sheets 連線
    try:
        client = gspread.authorize(creds)
        client.open_by_key(spreadsheet_id)
        status["Google Sheets"] = True
    except Exception:
        pass

    # 3. Google Drive 資料夾連線
    try:
        service = build('drive', 'v3', credentials=creds)
        service.files().get(fileId=folder_id).execute()
        status["Google Drive"] = True
    except Exception:
        pass
        
    return status

@st.cache_data(ttl=600)
def fetch_student_data(json_path, spreadsheet_id):
    """從 Google Sheets 獲取學生清單"""
    try:
        creds = Credentials.from_service_account_file(json_path, scopes=SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(spreadsheet_id).sheet1 # 假設在第一個分頁
        data = sheet.get_all_records()
        return data
    except Exception as e:
        st.error(f"資料讀取失敗: {e}")
        return []

# --- UI 介面 ---

st.set_page_config(page_title="校園管理系統", layout="centered")
st.title("🏫 校園管理資訊系統")

# 側邊欄：連線診斷
st.sidebar.header("🔍 系統連線診斷")
# 請替換為你的實際 ID
JSON_FILE = "credentials.json"
SHEET_ID = "你的Google_Sheet_ID"
FOLDER_ID = "你的Drive_Folder_ID"

diag = check_connections(JSON_FILE, SHEET_ID, FOLDER_ID)
for key, val in diag.items():
    if val:
        st.sidebar.success(f"● {key}: 已連線")
    else:
        st.sidebar.error(f"● {key}: 斷線或錯誤")

# 主頁面導覽
menu = ["首頁", "衛生糾察", "班級察看", "系統管理"]
choice = st.selectbox("請選擇功能介面", menu)

if choice == "首頁":
    st.info("歡迎使用本系統，請從上方選單選擇功能。")
    st.image("https://via.placeholder.com/600x200.png?text=Welcome+to+School+Management+System")

elif choice == "衛生糾察":
    pwd = st.text_input("請輸入衛生糾察通行碼", type="password")
    if pwd == PASSCODES["衛生糾察"]:
        st.success("驗證成功！進入衛生糾察頁面")
        st.divider()
        
        # 獲取資料
        raw_data = fetch_student_data(JSON_FILE, SHEET_ID)
        
        if raw_data:
            # 第一階層：年級
            grades = sorted(list(set(str(d['年級']) for d in raw_data)))
            selected_grade = st.selectbox("第一階層：選擇年級", grades)
            
            # 過濾該年級學生
            filtered_students = [d for d in raw_data if str(d['年級']) == selected_grade]
            
            # 第二階層：學號與姓名
            student_options = [f"{d['學號']} - {d['姓名']}" for d in filtered_students]
            selected_student = st.selectbox("第二階層：選擇學生 (學號 - 姓名)", student_options)
            
            st.write(f"📌 當前選取：{selected_student}")
            # 這裡可以接續開發評分功能...
    elif pwd != "":
        st.error("❌ 通行碼錯誤，請重新輸入")

elif choice == "班級察看":
    st.subheader("📊 班級狀態察看")
    st.write("此頁面無需通行碼，僅供一般瀏覽。")
    # 這裡可以放公開的統計圖表

elif choice == "系統管理":
    pwd = st.text_input("請輸入系統管理通行碼", type="password")
    if pwd == PASSCODES["系統管理"]:
        st.success("管理員您好，系統狀態正常。")
        # 這裡可以放置系統設定、日誌查看等功能
    elif pwd != "":
        st.error("❌ 通行碼錯誤，請重新輸入")
