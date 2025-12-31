# ==========================================
# TOOL QUẢN TRỊ SHOPEE - BCM VERSION 3.0 (CLOUD EDITION)
# Coder: BCM-Engineer & Sếp Lâm
# Database: Google Sheets (Không lo mất dữ liệu)
# ==========================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from google import genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CẤU HÌNH AI ---
AI_MODEL_ID = 'gemini-2.0-flash-exp' 

# --- CẤU HÌNH GOOGLE SHEETS ---
# Tên file Google Sheet Sếp đã tạo
SHEET_NAME = "bcm_database" 

# Hàm kết nối Google Sheets (Cache để đỡ load lại nhiều lần)
@st.cache_resource
def connect_to_sheets():
    # Phạm vi quyền hạn
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # Lấy thông tin mật khẩu từ st.secrets (Khi chạy trên Cloud)
    # Hoặc file json cục bộ (Khi chạy trên máy)
    try:
        # Ưu tiên lấy từ Secrets của Streamlit Cloud
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    except:
        # Nếu không có Secrets, tìm file json trên máy (đổi tên file json của Sếp thành credentials.json)
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        except:
            st.error("🚨 Không tìm thấy chìa khóa (Credentials)! Hãy thiết lập Secrets hoặc file JSON.")
            return None

    client = gspread.authorize(creds)
    try:
        sheet = client.open(SHEET_NAME)
        return sheet
    except:
        st.error(f"🚨 Không tìm thấy file Google Sheet tên là '{SHEET_NAME}'. Hãy tạo file và Share cho Robot!")
        return None

# --- CÁC HÀM XỬ LÝ DỮ LIỆU (DATABASE GOOGLE SHEETS) ---

def init_db():
    # Kiểm tra xem file Sheet đã có Header chuẩn chưa, nếu chưa thì tạo
    sh = connect_to_sheets()
    if sh:
        # 1. Setup Tab Products
        try:
            wks_prod = sh.worksheet("products")
        except:
            wks_prod = sh.add_worksheet(title="products", rows=100, cols=20)
        
        # Nếu dòng 1 trống, điền Header
        if not wks_prod.row_values(1):
            wks_prod.append_row(["id", "name", "cost_price", "selling_price", "stock_quantity", "alert_threshold", "daily_sales", "lead_time", "safety_stock"])

        # 2. Setup Tab Financials
        try:
            wks_fin = sh.worksheet("financials")
        except:
            wks_fin = sh.add_worksheet(title="financials", rows=100, cols=10)
        
        if not wks_fin.row_values(1):
            wks_fin.append_row(["date", "revenue", "ad_spend", "profit"])

# Gọi khởi tạo ngay
init_db()

def get_data_frame():
    sh = connect_to_sheets()
    wks = sh.worksheet("products")
    data = wks.get_all_records()
    if not data:
        return pd.DataFrame(columns=["id", "name", "cost_price", "selling_price", "stock_quantity", "alert_threshold", "daily_sales", "lead_time", "safety_stock"])
    return pd.DataFrame(data)

def add_product_to_db(name, cost, price, daily_sales, lead_time, safety):
    sh = connect_to_sheets()
    wks = sh.worksheet("products")
    
    # Tạo ID mới = số dòng hiện tại (đơn giản hóa)
    new_id = len(wks.get_all_values()) 
    threshold = int(daily_sales * lead_time + safety)
    
    wks.append_row([new_id, name, cost, price, 0, threshold, daily_sales, lead_time, safety])

def update_stock(product_id, amount):
    sh = connect_to_sheets()
    wks = sh.worksheet("products")
    
    # Tìm dòng chứa ID (Lưu ý: Sheet dòng 1 là Header)
    # Cách đơn giản: Load hết về tìm index.
    # Để tối ưu, ta giả định ID nằm ở cột 1.
    cell = wks.find(str(product_id), in_column=1)
    if cell:
        # Cột stock là cột số 5 (E)
        current_stock = int(wks.cell(cell.row, 5).value)
        new_stock = current_stock + amount
        wks.update_cell(cell.row, 5, new_stock)
    else:
        st.error("Không tìm thấy ID sản phẩm!")

def get_weekly_metrics(selected_date):
    start_date = (selected_date - timedelta(days=selected_date.weekday())).strftime("%Y-%m-%d")
    sh = connect_to_sheets()
    wks = sh.worksheet("financials")
    
    try:
        cell = wks.find(start_date, in_column=1)
        if cell:
            vals = wks.row_values(cell.row)
            # [date, revenue, ads, profit]
            return (int(vals[1]), int(vals[2]), int(vals[3]))
    except:
        pass
    return (0, 0, 0)

def save_weekly_metrics(selected_date, revenue, ads, profit):
    start_date = (selected_date - timedelta(days=selected_date.weekday())).strftime("%Y-%m-%d")
    sh = connect_to_sheets()
    wks = sh.worksheet("financials")
    
    try:
        cell = wks.find(start_date, in_column=1)
        if cell:
            # Update dòng cũ
            wks.update_cell(cell.row, 2, revenue)
            wks.update_cell(cell.row, 3, ads)
            wks.update_cell(cell.row, 4, profit)
        else:
            # Thêm dòng mới
            wks.append_row([start_date, revenue, ads, profit])
    except:
        wks.append_row([start_date, revenue, ads, profit])

# (Hàm xử lý file Excel Shopee giữ nguyên)
def process_shopee_files(revenue_file, ads_file):
    total_revenue = 0; total_ads = 0
    if revenue_file:
        try:
            df = pd.read_excel(revenue_file) if revenue_file.name.endswith('xls') or revenue_file.name.endswith('xlsx') else pd.read_csv(revenue_file)
            cols = [c for c in df.columns if "thành tiền" in str(c).lower() or "tổng tiền" in str(c).lower()]
            if cols:
                total_revenue = df[cols[0]].replace(r'[^\d.]', '', regex=True).apply(pd.to_numeric, errors='coerce').sum()
        except: pass
    if ads_file:
        try:
            df = pd.read_excel(ads_file) if ads_file.name.endswith('xls') or ads_file.name.endswith('xlsx') else pd.read_csv(ads_file)
            cols = [c for c in df.columns if "chi phí" in str(c).lower()]
            if cols:
                total_ads = df[cols[0]].replace(r'[^\d.]', '', regex=True).apply(pd.to_numeric, errors='coerce').sum()
        except: pass
    return total_revenue, total_ads

# --- GIAO DIỆN CHÍNH (GIỮ NGUYÊN) ---
st.set_page_config(page_title="BCM Cloud v3.0", page_icon="☁️", layout="wide")

# Sidebar cấu hình Key
st.sidebar.title("BCM v3.0 (Cloud)")
api_key = st.sidebar.text_input("🔑 Google AI Key:", type="password")
client = None
if api_key:
    try:
        client = genai.Client(api_key=api_key)
        st.sidebar.success("AI OK! 🟢")
    except: pass

menu = st.sidebar.radio("Menu:", ["💰 Tính Lãi & Thêm Mới", "🤖 Trợ Lý AI", "📊 Báo Cáo Tuần", "📦 Kho Hàng"])

# --- CÁC TAB CHỨC NĂNG (LOGIC NHƯ CŨ, CHỈ GỌI HÀM DB MỚI) ---
if menu == "💰 Tính Lãi & Thêm Mới":
    st.title("💰 TÍNH LÃI & LƯU CLOUD")
    c1, c2, c3 = st.columns(3)
    with c1:
        ten = st.text_input("Tên SP")
        von = st.number_input("Giá Vốn", step=1000)
    with c2:
        ban = st.number_input("Giá Bán", step=1000)
        hop = st.number_input("Phí đóng gói", value=2000)
    with c3:
        daily = st.number_input("Bán/ngày", value=1.0)
        lead = st.number_input("Ngày ship", value=15)
        safety = st.number_input("Tồn an toàn", value=5)
    
    phi_san = st.slider("Phí sàn %", 0, 25, 16)
    
    if st.button("🚀 TÍNH & LƯU"):
        lai = ban*(1-phi_san/100) - von - hop
        rop = int(daily*lead + safety)
        st.metric("LÃI RÒNG", f"{lai:,.0f} đ", f"ROP: {rop} cái")
        if lai > 0:
            add_product_to_db(ten, von, ban, daily, lead, safety)
            st.success(f"Đã lưu '{ten}' lên Google Sheet!")

elif menu == "🤖 Trợ Lý AI":
    st.title("🤖 AI STRATEGIST")
    if st.button("Phân tích tuần này"):
        if not client: st.error("Thiếu Key AI")
        else:
            rev, ads, prof = get_weekly_metrics(datetime.now())
            prompt = f"Phân tích tuần: Doanh thu {rev}, Ads {ads}, Lãi {prof}. Ngắn gọn."
            res = client.models.generate_content(model=AI_MODEL_ID, contents=prompt)
            st.write(res.text)

elif menu == "📊 Báo Cáo Tuần":
    st.title("📊 TRUNG TÂM DỮ LIỆU")
    d = st.date_input("Chọn tuần", datetime.now())
    rev, ads, prof = get_weekly_metrics(d)
    
    with st.expander("Upload Excel"):
        f1 = st.file_uploader("Doanh thu"); f2 = st.file_uploader("Ads")
        arev, aads = process_shopee_files(f1, f2)
    
    frev = arev if arev>0 else rev
    fads = aads if aads>0 else ads
    
    c1, c2, c3 = st.columns(3)
    n_rev = c1.number_input("Doanh thu", value=float(frev))
    n_ads = c2.number_input("Ads", value=float(fads))
    n_prof = c3.number_input("Lợi nhuận", value=float(prof))
    
    if st.button("💾 LƯU LÊN SHEET"):
        save_weekly_metrics(d, n_rev, n_ads, n_prof)
        st.success("Đã đồng bộ lên mây! ☁️")

elif menu == "📦 Kho Hàng":
    st.title("📦 KHO ONLINE")
    df = get_data_frame()
    if not df.empty:
        st.dataframe(df)
        with st.form("stock"):
            pid = st.selectbox("Chọn SP (ID)", df['id'])
            qty = st.number_input("Số lượng (+/-)", step=1)
            if st.form_submit_button("Cập nhật kho"):
                update_stock(pid, qty)
                st.rerun()
    else: st.warning("Kho trống trên Sheet.")
