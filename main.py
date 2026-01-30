import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime, timedelta
import random
import string
import io

# --- 1. 初始設定與 Secrets 讀取 ---
st.set_page_config(page_title="校園環境評分系統", layout="wide")

GCP_INFO = dict(st.secrets["gcp_service_account"])
CONFIG = st.secrets["system_config"]
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# 初始化 Session State
if 'auth_team' not in st.session_state: st.session_state.auth_team = False
if 'auth_admin' not in st.session_state: st.session_state.auth_admin = False
if 'deduction_score' not in st.session_state: st.session_state.deduction_score = 0

# --- 2. 核心 API 工具 ---

def get_creds():
    return Credentials.from_service_account_info(GCP_INFO, scopes=SCOPE)

def check_connections():
    """診斷系統連線狀態"""
    status = {"GCP憑證": False, "Google Sheets": False, "Google Drive": False}
    try:
        creds = get_creds()
        status["GCP憑證"] = True
        # Sheets 測試
        gspread.authorize(creds).open_by_key(CONFIG["sheet_id"])
        status["Google Sheets"] = True
        # Drive 測試 (使用 drive_folder_id)
        drive_service = build('drive', 'v3', credentials=creds)
        drive_service.files().get(fileId=CONFIG["drive_folder_id"]).execute()
        status["Google Drive"] = True
    except Exception as e:
        st.sidebar.warning(f"診斷細節: {e}")
    return status

@st.cache_data(ttl=60)
def fetch_sheet_data(worksheet_name):
    try:
        client = gspread.authorize(get_creds())
        sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet(worksheet_name)
        return sheet.get_all_records()
    except: return []

def calculate_week(target_date):
    try:
        client = gspread.authorize(get_creds())
        sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("settings")
        s_val = sheet.cell(sheet.find("semester_start").row, sheet.find("semester_start").col + 1).value
        start_date = datetime.strptime(s_val, '%Y-%m-%d').date()
        start_mon = start_date - timedelta(days=start_date.weekday())
        target_mon = target_date - timedelta(days=target_date.weekday())
        return (target_mon - start_mon).days // 7 + 1
    except: return 1

# --- 3. 側邊欄 UI ---
with st.sidebar:
    st.title("🛡️ 系統選單")
    choice = st.radio("請選擇模式", ["衛生糾察", "班級察看", "系統管理"])
    st.divider()
    st.subheader("🔍 系統連線診斷")
    diag = check_connections()
    for k, v in diag.items():
        st.write(f"{'🟢' if v else '🔴'} {k}")
        
    if "system_config" in st.secrets and "drive_folder_id" in CONFIG:
            st.success("✅ Drive 資料夾 ID 已設定")

# --- 4. 主頁面邏輯 ---
st.title("校園環境評分系統")

# --- 衛生糾察模式 ---
if choice == "衛生糾察":
    if not st.session_state.auth_team:
        pwd = st.text_input("輸入衛生糾察通行碼", type="password")
        if st.button("登入"):
            if pwd == CONFIG["team_password"]:
                st.session_state.auth_team = True
                st.rerun()
            else: st.error("❌ 通行碼錯誤")
    else:
        # A. 人員與日期
        inspectors = fetch_sheet_data("inspectors")
        grade_map = {"一年級": "1", "二年級": "2", "三年級": "3"}
        sel_grade = st.radio("請選擇年級", list(grade_map.keys()), horizontal=True)
        names = sorted([r['姓名'] for r in inspectors if str(r.get('班級', '')).startswith(grade_map[sel_grade])])
        curr_inspector = st.radio("請選擇您的姓名", names, horizontal=True) if names else "未知"
        st.info(f"👤 當前評分員：{curr_inspector}")
        st.divider()

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            ins_date = st.date_input("檢查日期", datetime.now().date())
        with col_d2:
            week_val = calculate_week(ins_date)
            st.metric("當前週次", f"第 {week_val} 週")

        # B. 受檢班級
        st.subheader("📍 選擇受檢班級")
        roster = fetch_sheet_data("roster")
        target_grade = st.radio("受檢年級", ["一年級", "二年級", "三年級"], horizontal=True, key="tg")
        t_classes = sorted(list(set([str(r['班級']) for r in roster if str(r.get('班級', '')).startswith(grade_map[target_grade])])))
        target_class = st.radio("受檢班級", t_classes, horizontal=True)
        
        if target_class:
            st.markdown(f"📍 正在評比班級：<span style='color:red; font-weight:bold; font-size:1.2em;'>{target_class}</span>", unsafe_allow_html=True)
        st.divider()

        # C. 區域與細項
        st.markdown("### 🗺️ 區域")
        area = st.radio("選擇區域", ["內掃", "外掃", "其他"], horizontal=True, label_visibility="collapsed")
        
        item_data = {
            "內掃": ["走廊", "洗手台", "門窗", "廚餘桶", "回收架", "掃具"],
            "外掃": ["地板及草坪", "掃具", "樓梯間", "落葉區", "回收架垃圾桶"],
            "其他": ["其他項目"]
        }
        selected_item = st.selectbox("選擇細項", item_options := item_data.get(area, ["其他項目"]))
        condition = st.selectbox("狀況", ["髒亂", "有垃圾", "有廚餘", "有蜘蛛網", "沒拖地"])
        remark = st.text_input("補充說明")

        # D. 扣分功能
        st.markdown("### 🔢 扣分金額")
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("➖"): st.session_state.deduction_score = max(0, st.session_state.deduction_score - 1)
        with c2:
            score = st.number_input("扣分", min_value=0, value=st.session_state.deduction_score, step=1, label_visibility="collapsed")
            st.session_state.deduction_score = score
        with c3:
            if st.button("➕"): st.session_state.deduction_score += 1

        # E. 照片上傳
        st.markdown("### 📸 違規照片 (若有扣分則必填)")
        files = st.file_uploader("可選取多個檔案，每個上限 10MB", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

        # F. 送出評分
        if st.button("🚀 送出評分"):
            if st.session_state.deduction_score > 0 and not files:
                st.error("⚠️ 偵測到扣分，請務必上傳違規照片。")
            else:
                try:
                    with st.spinner("正在儲存資料與處理圖片..."):
                        drive_service = build('drive', 'v3', credentials=get_creds())
                        photo_links = []
                        uploaded_names = []

                        for idx, f in enumerate(files):
                            # 檔名：年-月-日_班級_序號
                            ext = f.name.split('.')[-1]
                            new_name = f"{ins_date}_{target_class}_{idx:02d}.{ext}"
                            
                            media = MediaIoBaseUpload(io.BytesIO(f.read()), mimetype=f'image/{ext}')
                            f_meta = {'name': new_name, 'parents': [CONFIG["drive_folder_id"]]}
                            
                            up_file = drive_service.files().create(body=f_meta, media_body=media, fields='id').execute()
                            fid = up_file.get('id')
                            
                            # 設定共用權限
                            drive_service.permissions().create(fileId=fid, body={'type': 'anyone', 'role': 'reader'}).execute()
                            
                            # 產生縮圖網址
                            photo_links.append(f"https://drive.google.com/thumbnail?id={fid}&sz=w1000")
                            uploaded_names.append(new_name)

                        # 產出紀錄 ID 與時間
                        now = datetime.now()
                        rand_code = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
                        record_id = f"{now.strftime('%Y%m%d%H%M%S')}_{rand_code}"
                        
                        # 寫入 Google Sheets
                        client = gspread.authorize(get_creds())
                        main_sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("main_data")
                        
                        main_sheet.append_row([
                            str(ins_date),          # 日期
                            str(week_val),          # 週次
                            str(target_class),      # 班級
                            str(curr_inspector),    # 檢查人員
                            area,                   # 區域
                            f"{selected_item} {condition}", # 違規細項 (串接半形空白)
                            remark,                 # 補充說明
                            score,                  # 扣分值
                            ";".join(photo_links),  # 照片路徑 (分號區隔)
                            now.strftime('%Y-%m-%d %H:%M:%S'), # 登錄時間
                            record_id               # 紀錄ID
                        ])
                        
                        st.success("✅ 資料紀錄完成。")
                        for n in uploaded_names: st.write(f"📁 已上傳檔案：{n}")
                        st.session_state.deduction_score = 0 # 重置
                except Exception as ex:
                    st.error(f"❌ 失敗：{ex}")

# --- 系統管理模式 ---
elif choice == "系統管理":
    if not st.session_state.auth_admin:
        pwd = st.text_input("輸入管理密碼", type="password")
        if st.button("管理登入"):
            if pwd == CONFIG["admin_password"]:
                st.session_state.auth_admin = True
                st.rerun()
    else:
        tabs = st.tabs(["進度監控", "成績總表", "扣分明細", "寄送通知", "申訴審核", "系統設定", "名單更新"])
        with tabs[5]: # 系統設定
            st.subheader("⚙️ 開學日期設定")
            try:
                client = gspread.authorize(get_creds())
                set_sheet = client.open_by_key(CONFIG["sheet_id"]).worksheet("settings")
                cell = set_sheet.find("semester_start")
                old_date = datetime.strptime(set_sheet.cell(cell.row, cell.col + 1).value, '%Y-%m-%d').date()
                
                new_date = st.date_input("修改開學日", old_date)
                if st.button("更新開學日"):
                    set_sheet.update_cell(cell.row, cell.col + 1, str(new_date))
                    st.success("更新成功！")
                    st.cache_data.clear()
            except: st.error("設定頁籤讀取異常")
