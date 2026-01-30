import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime, timedelta
import random
import string
import io

# --- 網頁初始設定 ---
st.set_page_config(page_title="校園環境評分系統", layout="wide")

# --- 讀取 Secrets ---
GCP_INFO = dict(st.secrets["gcp_service_account"])
CONFIG = st.secrets["system_config"]
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# --- 初始化 Session State ---
if 'auth_team' not in st.session_state: st.session_state.auth_team = False
if 'auth_admin' not in st.session_state: st.session_state.auth_admin = False
if 'score' not in st.session_state: st.session_state.score = 0

# --- 工具函式 ---
def get_gspread_client():
    creds = Credentials.from_service_account_info(GCP_INFO, scopes=SCOPE)
    return gspread.authorize(creds)

def get_drive_service():
    creds = Credentials.from_service_account_info(GCP_INFO, scopes=SCOPE)
    return build('drive', 'v3', credentials=creds,cache_discovery=False)

def get_connection_status():
    status = {"GCP憑證": False, "Google Sheets": False, "Google Drive": False}
    try:
        creds = Credentials.from_service_account_info(GCP_INFO, scopes=SCOPE)
        status["GCP憑證"] = True
        get_gspread_client().open_by_key(CONFIG["sheet_id"])
        status["Google Sheets"] = True
        get_drive_service().files().get(fileId=CONFIG["drive_folder_id"]).execute()
        status["Google Drive"] = True
        st.info(fCONFIG["drive_folder_id"])
    except: pass
    return status

@st.cache_data(ttl=60)
def fetch_sheet_data(worksheet_name):
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet(worksheet_name)
        return sheet.get_all_records()
    except: return []

def calculate_week(target_date):
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("settings")
        s_val = sheet.cell(sheet.find("semester_start").row, sheet.find("semester_start").col + 1).value
        start_date = datetime.strptime(s_val, '%Y-%m-%d').date()
        start_monday = start_date - timedelta(days=start_date.weekday())
        target_monday = target_date - timedelta(days=target_date.weekday())
        return (target_monday - start_monday).days // 7 + 1
    except: return "N/A"

# --- 側邊欄 ---
with st.sidebar:
    st.title("🛡️ 系統選單")
    choice = st.radio("請選擇模式", ["衛生糾察", "班級察看", "系統管理"])
    st.divider()
    st.subheader("🔍 系統連線診斷")
    diag = get_connection_status()
    for k, v in diag.items():
        st.write(f"{'🟢' if v else '🔴'} {k}")

# --- 主頁面 ---
st.title("校園環境評分系統")

if choice == "衛生糾察":
    if not st.session_state.auth_team:
        pwd = st.text_input("輸入衛生糾察通行碼", type="password")
        if st.button("登入"):
            if pwd == CONFIG["team_password"]:
                st.session_state.auth_team = True
                st.rerun()
            else: st.error("❌ 通行碼錯誤")
    else:
        # 1. 人員選擇
        inspectors = fetch_sheet_data("inspectors")
        grade_map = {"一年級": "1", "二年級": "2", "三年級": "3"}
        sel_grade = st.radio("請選擇年級", list(grade_map.keys()), horizontal=True)
        names = sorted([r['姓名'] for r in inspectors if str(r.get('班級', '')).startswith(grade_map[sel_grade])])
        
        selected_name = st.radio("請選擇您的姓名", names, horizontal=True) if names else "無資料"
        st.info(f"👤 當前評分員：{selected_name}")
        st.divider()

        # 2. 日期與週次
        col1, col2 = st.columns(2)
        with col1:
            ins_date = st.date_input("檢查日期", datetime.now().date())
        with col2:
            week_num = calculate_week(ins_date)
            st.metric("當前週次", f"第 {week_num} 週")

        # 3. 受檢班級
        st.subheader("📍 選擇受檢班級")
        roster = fetch_sheet_data("roster")
        t_grade = st.radio("受檢年級", ["一年級", "二年級", "三年級"], horizontal=True, key="tg")
        t_classes = sorted(list(set([str(r['班級']) for r in roster if str(r.get('班級', '')).startswith(grade_map[t_grade])])))
        selected_class = st.radio("受檢班級", t_classes, horizontal=True)
        
        if selected_class:
            st.markdown(f"📍 正在評比班級：<span style='color:red; font-weight:bold;'>{selected_class}</span>", unsafe_allow_html=True)
        st.divider()

        # 4. 評分細項
        st.subheader("📝 評分內容")
        region = st.radio("區域", ["內掃", "外掃", "其他"], horizontal=True)
        
        item_options = {
            "內掃": ["走廊", "洗手台", "門窗", "廚餘桶", "回收架", "掃具"],
            "外掃": ["地板及草坪", "掃具", "樓梯間", "落葉區", "回收架垃圾桶"],
            "其他": ["其他項目"]
        }
        selected_item = st.selectbox("項目", item_options[region])
        condition = st.selectbox("狀況", ["髒亂", "有垃圾", "有廚餘", "有蜘蛛網", "沒拖地"])
        remarks = st.text_input("補充說明")

        # 5. 扣分功能 (加減按鈕)
        st.write("扣分欄位")
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("➖"): st.session_state.score = max(0, st.session_state.score - 1)
        with c2:
            st.session_state.score = st.number_input("扣分分值", min_value=0, value=st.session_state.score, step=1, label_visibility="collapsed")
        with c3:
            if st.button("➕"): st.session_state.score += 1

        # 6. 照片上傳
        uploaded_files = st.file_uploader("違規照片(若有扣分則必填)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
        
        # 7. 送出評分
        if st.button("🚀 送出評分"):
            if st.session_state.score > 0 and not uploaded_files:
                st.error("⚠️ 有扣分時必須上傳照片")
            else:
                try:
                    with st.spinner("正在上傳資料與照片..."):
                        drive_service = get_drive_service()
                        photo_urls = []
                        file_names = []
                        
                        # 上傳照片
                        for idx, file in enumerate(uploaded_files):
                            if file.size > 10 * 1024 * 1024:
                                st.error(f"檔案 {file.name} 超過 10MB")
                                continue
                            
                            file_ext = file.name.split('.')[-1]
                            new_filename = f"{ins_date}_{selected_class}_{idx:02d}.{file_ext}"
                            
                            file_metadata = {'name': new_filename, 'parents': [CONFIG["drive_folder_id"]]}
                            media = MediaIoBaseUpload(io.BytesIO(file.read()), mimetype=f'image/{file_ext}')
                            uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                            file_id = uploaded_file.get('id')
                            
                            # 設定權限為任何人可讀
                            drive_service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
                            
                            photo_urls.append(f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000")
                            file_names.append(new_filename)

                        # 產生紀錄ID
                        rand_id = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
                        record_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{rand_id}"
                        
                        # 寫入 Google Sheets
                        client = get_gspread_client()
                        main_sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("main_data")
                        
                        row_data = [
                            str(ins_date),                 # 日期
                            f"第{week_num}週",             # 週次
                            str(selected_class),           # 班級
                            str(selected_name),            # 檢查人員
                            region,                        # 區域
                            f"{selected_item} {condition}",# 違規細項
                            remarks,                       # 補充說明
                            st.session_state.score,        # 扣分 (自加欄位)
                            ";".join(photo_urls),          # 照片路徑
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), # 登錄時間
                            record_id                      # 紀錄ID
                        ]
                        main_sheet.append_row(row_data)
                        
                        st.success("✅ 資料紀錄完成。")
                        for fn in file_names: st.write(f"📄 已上傳: {fn}")
                        st.session_state.score = 0 # 重置分數
                except Exception as e:
                    st.error(f"❌ 失敗: {str(e)}")

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
        with tabs[6]: # 名單更新
            st.json({
            "Sheet ID": CONFIG["sheet_id"],
            "Folder ID": CONFIG["drive_folder_id"],
            "GCP Project": GCP_INFO["project_id"]
        })
