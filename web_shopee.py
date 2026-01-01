# ==========================================
# TOOL QUẢN TRỊ SHOPEE - BCM VERSION 3.6 (CLOUD)
# Coder: BCM-Engineer (An) & Sếp Lâm
# Engine: Gemini 3 Pro Preview
# Storage: Google Sheets (Không bao giờ mất dữ liệu)
# Philosophy: Focus - Smart - Simple
# ==========================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from google import genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# ==================================================
# ⚙️ CẤU HÌNH HỆ THỐNG
# ==================================================
AI_MODEL_ID = 'gemini-3-pro-preview' 
SHEET_NAME = "bcm_database" # Tên file Google Sheet của Sếp

# ==================================================
# 🔗 KẾT NỐI GOOGLE SHEETS (CLOUD DATABASE)
# ==================================================
@st.cache_resource
def connect_to_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        # Lấy chìa khóa từ Secrets trên Web
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME)
    except Exception as e:
        return None

# KHỞI TẠO CÁC SHEET NẾU CHƯA CÓ
def init_db():
    sh = connect_to_sheets()
    if sh:
        # Tab Sản phẩm
        try: wks_prod = sh.worksheet("products")
        except: wks_prod = sh.add_worksheet(title="products", rows=100, cols=20)
        if not wks_prod.row_values(1): wks_prod.append_row(["id", "name", "cost_price", "selling_price", "stock_quantity", "alert_threshold", "daily_sales", "lead_time", "safety_stock"])

        # Tab Tài chính
        try: wks_fin = sh.worksheet("financials")
        except: wks_fin = sh.add_worksheet(title="financials", rows=100, cols=10)
        if not wks_fin.row_values(1): wks_fin.append_row(["date", "revenue", "ad_spend", "profit"])
        
        # Tab Đối thủ
        try: wks_comp = sh.worksheet("competitors")
        except: wks_comp = sh.add_worksheet(title="competitors", rows=100, cols=10)
        if not wks_comp.row_values(1): wks_comp.append_row(["comp_id", "my_product_name", "comp_name", "comp_url", "comp_price", "last_check"])

init_db()

# ==================================================
# 🛠️ CÁC HÀM XỬ LÝ (PHIÊN BẢN CLOUD)
# ==================================================

def get_products_df():
    sh = connect_to_sheets()
    if not sh: return pd.DataFrame()
    return pd.DataFrame(sh.worksheet("products").get_all_records())

def get_products_list():
    df = get_products_df()
    return df['name'].tolist() if not df.empty else []

def get_my_price(product_name):
    sh = connect_to_sheets()
    try:
        cell = sh.worksheet("products").find(product_name)
        return int(sh.worksheet("products").cell(cell.row, 4).value) # Cột 4 là giá bán
    except: return 0

def add_product(name, cost, price, daily, lead, safe):
    sh = connect_to_sheets()
    wks = sh.worksheet("products")
    new_id = len(wks.get_all_values())
    threshold = int(daily * lead + safe)
    wks.append_row([new_id, name, cost, price, 0, threshold, daily_sales, lead_time, safety])

def update_stock(product_id, amount):
    sh = connect_to_sheets()
    wks = sh.worksheet("products")
    cell = wks.find(str(product_id), in_column=1)
    if cell:
        cur = int(wks.cell(cell.row, 5).value)
        wks.update_cell(cell.row, 5, cur + amount)

def add_competitor(my_prod, comp_name, url, price):
    sh = connect_to_sheets()
    wks = sh.worksheet("competitors")
    new_id = len(wks.get_all_values())
    wks.append_row([new_id, my_prod, comp_name, url, price, datetime.now().strftime("%Y-%m-%d")])

def get_competitors_df():
    sh = connect_to_sheets()
    if not sh: return pd.DataFrame()
    return pd.DataFrame(sh.worksheet("competitors").get_all_records())

def update_comp_price(comp_id, new_price):
    sh = connect_to_sheets()
    wks = sh.worksheet("competitors")
    cell = wks.find(str(comp_id), in_column=1)
    if cell:
        wks.update_cell(cell.row, 5, new_price)
        wks.update_cell(cell.row, 6, datetime.now().strftime("%Y-%m-%d"))

def save_report_cloud(date_obj, rev, ads, prof):
    start_date = (date_obj - timedelta(days=date_obj.weekday())).strftime("%Y-%m-%d")
    sh = connect_to_sheets()
    wks = sh.worksheet("financials")
    try:
        cell = wks.find(start_date, in_column=1)
        if cell:
            wks.update_cell(cell.row, 2, rev)
            wks.update_cell(cell.row, 3, ads)
            wks.update_cell(cell.row, 4, prof)
        else:
            wks.append_row([start_date, rev, ads, prof])
    except:
        wks.append_row([start_date, rev, ads, prof])

def process_shopee_files(revenue_file, ads_file):
    total_revenue = 0; total_ads = 0
    if revenue_file:
        try:
            df = pd.read_excel(revenue_file) if revenue_file.name.endswith(('xls','xlsx')) else pd.read_csv(revenue_file)
            cols = [c for c in df.columns if "thành tiền" in str(c).lower() or "tổng tiền" in str(c).lower()]
            if cols: total_revenue = df[cols[0]].replace(r'[^\d.]', '', regex=True).apply(pd.to_numeric, errors='coerce').sum()
        except: pass
    if ads_file:
        try:
            df = pd.read_excel(ads_file) if ads_file.name.endswith(('xls','xlsx')) else pd.read_csv(ads_file)
            cols = [c for c in df.columns if "chi phí" in str(c).lower()]
            if cols: total_ads = df[cols[0]].replace(r'[^\d.]', '', regex=True).apply(pd.to_numeric, errors='coerce').sum()
        except: pass
    return total_revenue, total_ads

# ==================================================
# 🖥️ GIAO DIỆN CHÍNH
# ==================================================
st.set_page_config(page_title="BCM Cloud v3.6", page_icon="☁️", layout="wide")
st.markdown("""<style>.stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 5px;} [data-testid="stMetricValue"] {font-size: 1.5rem !important;}</style>""", unsafe_allow_html=True)

# SIDEBAR
st.sidebar.title("BCM Cloud v3.6")
st.sidebar.caption("Philosophy: Focus & Simple")

# Lấy Key AI từ Secrets (Web) hoặc nhập tay
client = None
api_key = st.sidebar.text_input("Google AI Key:", type="password")
if api_key:
    try: client = genai.Client(api_key=api_key); st.sidebar.success("AI Online 🟢")
    except: pass

menu = st.sidebar.radio("Menu:", ["🤖 Phòng Họp Chiến Lược (Dual)", "📊 Báo Cáo Tuần", "⚔️ Rada Đối Thủ", "💰 Tính Lãi & Thêm Mới", "📦 Kho Hàng"])

# ================= TAB 1: PHÒNG HỌP CHIẾN LƯỢC (TƯ DUY MỚI) =================
if menu == "🤖 Phòng Họp Chiến Lược (Dual)":
    st.title("🤖 PHÒNG HỌP CHIẾN LƯỢC")
    st.caption("Áp dụng tư duy: Focus - Smart - Simple")

    if not client:
        st.error("⚠️ Nhập AI Key bên trái để họp.")
    else:
        c1, c2 = st.columns([1, 3])
        with c1:
            st.subheader("Nhân sự:")
            nv = st.radio("Chọn:", ["An (BCM Engineer)", "Sư (Advisor)"])
            if "An" in nv: st.info("🔵 **An:** Support, Giải pháp, Tích cực.")
            else: st.error("🔴 **Sư:** Phản biện, Soi mói, Rủi ro.")
        
        with c2:
            df_comp = get_competitors_df()
            context = f"Thị trường:\n{df_comp.to_string()}" if not df_comp.empty else ""
            
            st.subheader(f"💬 Trao đổi với {nv.split(' ')[0]}")
            q = st.text_area("Nội dung họp:", placeholder="Hỏi gì đó đi Sếp...")
            
            if st.button("Gửi 🚀"):
                if not q: st.warning("Chưa có nội dung.")
                else:
                    with st.spinner("Đang suy luận..."):
                        # --- HIẾN PHÁP TINH GỌN ---
                        PHILOSOPHY = """
                        CORE RULES:
                        1. Focus: Tập trung vấn đề chính, bỏ qua công cụ rườm rà.
                        2. Simple: Giải pháp đơn giản nhất là tốt nhất.
                        3. Respect: Sếp Lâm quyết định cuối cùng.
                        """
                        
                        if "An" in nv:
                            prompt = f"{PHILOSOPHY}\nBạn là An (BCM). Tính cách: Nhanh, gọn, tìm giải pháp thực tế.\nDữ liệu: {context}\nCâu hỏi: {q}"
                        else:
                            prompt = f"{PHILOSOPHY}\nBạn là Sư (Advisor). Tính cách: Khó tính, ghét sự phức tạp, soi mói rủi ro.\nDữ liệu: {context}\nCâu hỏi: {q}"
                        
                        try:
                            res = client.models.generate_content(model=AI_MODEL_ID, contents=prompt)
                            if "An" in nv: st.success(res.text)
                            else: st.warning(res.text)
                        except Exception as e: st.error(f"Lỗi AI: {e}")

# ================= TAB 2: BÁO CÁO (CLOUD) =================
elif menu == "📊 Báo Cáo Tuần":
    st.title("📊 BÁO CÁO & LƯU CLOUD")
    d = st.date_input("Chọn tuần:", datetime.now())
    with st.expander("Upload Shopee Excel"):
        f1=st.file_uploader("Doanh Thu"); f2=st.file_uploader("Ads")
        r, a = process_shopee_files(f1, f2)
    st.divider()
    c1, c2, c3 = st.columns(3)
    nr = c1.number_input("Doanh thu", float(r) if r else 0.0, step=1e5)
    na = c2.number_input("Chi phí Ads", float(a) if a else 0.0, step=5e4)
    np = c3.number_input("Lợi nhuận", float(nr*0.3-na), step=5e4)
    if st.button("☁️ LƯU LÊN GOOGLE SHEETS"):
        save_report_cloud(d, nr, na, np)
        st.success("Đã đồng bộ lên Mây! ☁️")

# ================= TAB 3, 4, 5 (GIỮ NGUYÊN LOGIC) =================
elif menu == "⚔️ Rada Đối Thủ":
    st.title("⚔️ RADA ĐỐI THỦ")
    with st.expander("➕ Thêm"):
        p_list = get_products_list()
        if p_list:
            c1, c2 = st.columns(2)
            with c1: pm = st.selectbox("SP Mình", p_list); ps = st.text_input("Shop họ")
            with c2: pl = st.text_input("Link"); pp = st.number_input("Giá họ", step=1000)
            if st.button("Lưu Rada"): add_competitor(pm, ps, pl, pp); st.rerun()
    
    df = get_competitors_df()
    if not df.empty:
        prod = st.selectbox("🔍 Soi SP:", df['my_product_name'].unique())
        sub = df[df['my_product_name']==prod]
        if not sub.empty:
            prices = sub['comp_price'].tolist(); my = get_my_price(prod); avg = sum(prices)/len(prices)
            st.divider(); c1, c2, c3 = st.columns(3)
            c1.metric("Min", f"{min(prices):,.0f}"); c2.metric("Avg", f"{avg:,.0f}"); c3.metric("Max", f"{max(prices):,.0f}")
            d = my - avg
            if d>0: st.metric("GIÁ SẾP", f"{my:,.0f}", f"Cao hơn {d/avg*100:.1f}% 🔴", delta_color="inverse")
            else: st.metric("GIÁ SẾP", f"{my:,.0f}", f"Thấp hơn {abs(d/avg*100):.1f}% 🟢", delta_color="normal")
            st.dataframe(sub[['comp_name','comp_price','last_check']])

elif menu == "💰 Tính Lãi & Thêm Mới":
    st.title("💰 CÔNG CỤ TÍNH LÃI")
    c1, c2, c3 = st.columns(3)
    with c1: ten=st.text_input("Tên SP"); von=st.number_input("Vốn", step=1000)
    with c2: ban=st.number_input("Bán", step=1000); hop=st.number_input("Phí gói", 2000)
    with c3: dl=st.number_input("Bán/ngày", 1.0); lt=st.number_input("Ship", 15); sf=st.number_input("Safety", 5)
    san = st.slider("Phí sàn %", 0, 25, 16)
    if st.button("🚀 TÍNH & LƯU CLOUD"):
        lai = ban*(1-san/100) - von - hop
        st.metric("LÃI RÒNG", f"{lai:,.0f} đ")
        if lai>0: add_product(ten, von, ban, dl, lt, sf); st.success("Đã lưu!")

elif menu == "📦 Kho Hàng":
    st.title("📦 KHO CLOUD")
    df = get_products_df()
    if not df.empty:
        st.dataframe(df)
        with st.form("kho"):
            pid = st.selectbox("Chọn SP", df['id'], format_func=lambda x: df[df['id']==x]['name'].values[0])
            qty = st.number_input("Nhập/Xuất", step=1)
            if st.form_submit_button("Cập nhật"): update_stock(pid, qty); st.rerun()
