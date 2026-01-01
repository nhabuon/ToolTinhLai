# ==========================================
# TOOL QUẢN TRỊ SHOPEE - BCM VERSION 3.2 (FULL SYSTEM)
# Coder: BCM-Engineer & Sếp Lâm
# Tính năng: Tính lãi + Kho Cloud + AI + Radar Đối Thủ (Phân tích thị trường)
# ==========================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from google import genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- 1. CẤU HÌNH HỆ THỐNG ---
AI_MODEL_ID = 'gemini-3-pro-preview' 
SHEET_NAME = "bcm_database" 

# --- 2. KẾT NỐI GOOGLE SHEETS (CLOUD DATABASE) ---
@st.cache_resource
def connect_to_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # Ưu tiên lấy từ Secrets (khi chạy trên Web)
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    except:
        # Nếu lỗi, thử tìm file json trên máy (khi chạy local)
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        except:
            return None

    client = gspread.authorize(creds)
    try:
        return client.open(SHEET_NAME)
    except:
        return None

# --- 3. KHỞI TẠO DATABASE (AUTO TẠO SHEET NẾU CHƯA CÓ) ---
def init_db():
    sh = connect_to_sheets()
    if sh:
        # Tab 1: Sản phẩm (products)
        try: wks_prod = sh.worksheet("products")
        except: wks_prod = sh.add_worksheet(title="products", rows=100, cols=20)
        if not wks_prod.row_values(1): 
            wks_prod.append_row(["id", "name", "cost_price", "selling_price", "stock_quantity", "alert_threshold", "daily_sales", "lead_time", "safety_stock"])

        # Tab 2: Tài chính (financials)
        try: wks_fin = sh.worksheet("financials")
        except: wks_fin = sh.add_worksheet(title="financials", rows=100, cols=10)
        if not wks_fin.row_values(1): 
            wks_fin.append_row(["date", "revenue", "ad_spend", "profit"])
        
        # Tab 3: Đối thủ (competitors)
        try: wks_comp = sh.worksheet("competitors")
        except: wks_comp = sh.add_worksheet(title="competitors", rows=100, cols=10)
        if not wks_comp.row_values(1): 
            wks_comp.append_row(["comp_id", "my_product_name", "comp_name", "comp_url", "comp_price", "last_check"])

init_db()

# --- 4. CÁC HÀM XỬ LÝ DỮ LIỆU ---

# --- Nhóm Hàm Sản Phẩm & Kho ---
def get_data_frame():
    sh = connect_to_sheets()
    if not sh: return pd.DataFrame()
    return pd.DataFrame(sh.worksheet("products").get_all_records())

def get_products_list():
    df = get_data_frame()
    return df['name'].tolist() if not df.empty else []

def get_my_price(product_name):
    sh = connect_to_sheets()
    try:
        cell = sh.worksheet("products").find(product_name)
        # Giá bán ở cột 4 (D)
        return int(sh.worksheet("products").cell(cell.row, 4).value)
    except: return 0

def add_product_to_db(name, cost, price, daily_sales, lead_time, safety):
    sh = connect_to_sheets()
    wks = sh.worksheet("products")
    new_id = len(wks.get_all_values())
    threshold = int(daily_sales * lead_time + safety)
    wks.append_row([new_id, name, cost, price, 0, threshold, daily_sales, lead_time, safety])

def update_stock(product_id, amount):
    sh = connect_to_sheets()
    wks = sh.worksheet("products")
    cell = wks.find(str(product_id), in_column=1)
    if cell:
        cur = int(wks.cell(cell.row, 5).value)
        wks.update_cell(cell.row, 5, cur + amount)

# --- Nhóm Hàm Radar Đối Thủ ---
def add_competitor(my_prod, comp_name, url, price):
    sh = connect_to_sheets()
    wks = sh.worksheet("competitors")
    new_id = len(wks.get_all_values())
    wks.append_row([new_id, my_prod, comp_name, url, price, datetime.now().strftime("%Y-%m-%d")])

def get_competitors_df():
    sh = connect_to_sheets()
    if not sh: return pd.DataFrame()
    return pd.DataFrame(sh.worksheet("competitors").get_all_records())

def update_competitor_price(comp_id, new_price):
    sh = connect_to_sheets()
    wks = sh.worksheet("competitors")
    cell = wks.find(str(comp_id), in_column=1)
    if cell:
        wks.update_cell(cell.row, 5, new_price)
        wks.update_cell(cell.row, 6, datetime.now().strftime("%Y-%m-%d"))

# --- Nhóm Hàm Tài Chính ---
def get_weekly_metrics(selected_date):
    start_date = (selected_date - timedelta(days=selected_date.weekday())).strftime("%Y-%m-%d")
    sh = connect_to_sheets()
    wks = sh.worksheet("financials")
    try:
        cell = wks.find(start_date, in_column=1)
        if cell:
            vals = wks.row_values(cell.row)
            return (int(vals[1]), int(vals[2]), int(vals[3]))
    except: pass
    return (0, 0, 0)

def save_weekly_metrics(selected_date, revenue, ads, profit):
    start_date = (selected_date - timedelta(days=selected_date.weekday())).strftime("%Y-%m-%d")
    sh = connect_to_sheets()
    wks = sh.worksheet("financials")
    try:
        cell = wks.find(start_date, in_column=1)
        if cell:
            wks.update_cell(cell.row, 2, revenue)
            wks.update_cell(cell.row, 3, ads)
            wks.update_cell(cell.row, 4, profit)
        else:
            wks.append_row([start_date, revenue, ads, profit])
    except:
        wks.append_row([start_date, revenue, ads, profit])

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


# --- 5. GIAO DIỆN CHÍNH (STREAMLIT UI) ---
st.set_page_config(page_title="BCM System v3.2", page_icon="🦅", layout="wide")
st.markdown("""<style>.stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 5px;} [data-testid="stMetricValue"] {font-size: 1.5rem !important;}</style>""", unsafe_allow_html=True)

# SIDEBAR
st.sidebar.title("BCM v3.2 (Radar)")
api_key = st.sidebar.text_input("🔑 Google AI Key:", type="password")
client = None
if api_key:
    try: client = genai.Client(api_key=api_key); st.sidebar.success("AI Online 🟢")
    except: pass

menu = st.sidebar.radio("Menu:", ["⚔️ Rada & Thị Trường", "💰 Tính Lãi & Thêm Mới", "📊 Báo Cáo Tuần", "🤖 Trợ Lý AI", "📦 Kho Hàng"])

# ================= TAB 1: RADA ĐỐI THỦ (ĐÃ NÂNG CẤP) =================
if menu == "⚔️ Rada & Thị Trường":
    st.title("⚔️ PHÂN TÍCH THỊ TRƯỜNG & ĐỐI THỦ")
    
    # Khu vực thêm đối thủ
    with st.expander("➕ Thêm Đối Thủ Mới (Nhập đủ 5 ông)", expanded=False):
        my_prods = get_products_list()
        if not my_prods: st.warning("Kho trống! Vào tab 'Tính Lãi' tạo SP trước.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                p_me = st.selectbox("Sản phẩm mình:", my_prods)
                p_shop = st.text_input("Tên Shop họ:")
            with c2:
                p_link = st.text_input("Link Shopee:")
                p_price = st.number_input("Giá họ bán:", step=1000)
            if st.button("Lưu Rada"):
                add_competitor(p_me, p_shop, p_link, p_price)
                st.success("Đã lưu!"); time.sleep(1); st.rerun()
    
    # Khu vực phân tích
    df_comp = get_competitors_df()
    if not df_comp.empty:
        u_prods = df_comp['my_product_name'].unique()
        view_prod = st.selectbox("🔍 Chọn sản phẩm để soi:", u_prods)
        df_view = df_comp[df_comp['my_product_name'] == view_prod]
        
        if not df_view.empty:
            prices = df_view['comp_price'].tolist()
            my_price = get_my_price(view_prod)
            
            # Tính toán Min-Max-Avg
            min_p, max_p = min(prices), max(prices)
            avg_p = sum(prices)/len(prices)
            
            st.divider()
            st.subheader(f"📊 Thị Trường: {view_prod}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Giá Đáy (Min)", f"{min_p:,.0f}")
            m2.metric("Giá Trung Bình", f"{avg_p:,.0f}")
            m3.metric("Giá Trần (Max)", f"{max_p:,.0f}")
            
            delta = my_price - avg_p
            pct = (delta/avg_p*100) if avg_p>0 else 0
            if delta > 0: m4.metric("GIÁ CỦA SẾP", f"{my_price:,.0f}", f"Cao hơn {pct:.1f}% 🔴", delta_color="inverse")
            else: m4.metric("GIÁ CỦA SẾP", f"{my_price:,.0f}", f"Thấp hơn {abs(pct):.1f}% 🟢", delta_color="normal")
            
            if len(prices) < 5: st.warning(f"⚠️ Mới có {len(prices)} đối thủ. Cần thêm {5-len(prices)} nữa để AI tính chuẩn.")
            
            st.write("---")
            for idx, row in df_view.iterrows():
                diff = my_price - row['comp_price']
                pc = (diff/my_price*100) if my_price>0 else 0
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                    with c1: st.write(f"**{row['comp_name']}**"); st.caption(row['comp_url'])
                    with c2: st.metric("Giá Họ", f"{row['comp_price']:,.0f}")
                    with c3: 
                        if diff>0: st.metric("So với Sếp", "Rẻ hơn", f"{pc:.1f}%", delta_color="normal")
                        else: st.metric("So với Sếp", "Đắt hơn", f"{abs(pc):.1f}%", delta_color="inverse")
                    with c4:
                        np = st.number_input("Update giá", value=row['comp_price'], key=f"p_{row['comp_id']}", label_visibility="collapsed")
                        if st.button("Lưu", key=f"b_{row['comp_id']}"):
                            update_competitor_price(row['comp_id'], np); st.rerun()

# ================= TAB 2: TÍNH LÃI (CORE) =================
elif menu == "💰 Tính Lãi & Thêm Mới":
    st.title("💰 CÔNG CỤ TÍNH LÃI")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1: ten=st.text_input("Tên SP"); von=st.number_input("Giá Vốn", step=1000)
        with c2: ban=st.number_input("Giá Bán", step=1000); hop=st.number_input("Phí đóng gói", value=2000)
        with c3: daily=st.number_input("Bán/ngày", value=1.0); lead=st.number_input("Ngày ship", 15); safe=st.number_input("Safety Stock", 5)
        san = st.slider("Phí sàn %", 0, 25, 16)
        if st.button("🚀 TÍNH & LƯU"):
            lai = ban*(1-san/100) - von - hop
            rop = int(daily*lead + safe)
            st.divider()
            k1, k2 = st.columns(2)
            k1.metric("LÃI RÒNG", f"{lai:,.0f} đ", delta_color="normal" if lai>0 else "inverse")
            k2.metric("ĐIỂM NHẬP HÀNG", f"{rop} cái")
            if lai>0:
                add_product_to_db(ten, von, ban, daily, lead, safe)
                st.success("Đã lưu vào Cloud!")

# ================= TAB 3: BÁO CÁO =================
elif menu == "📊 Báo Cáo Tuần":
    st.title("📊 TRUNG TÂM CHỈ HUY")
    d = st.date_input("Chọn tuần", datetime.now())
    rev, ads, prof = get_weekly_metrics(d)
    with st.expander("Upload Excel Shopee"):
        f1=st.file_uploader("File Doanh Thu"); f2=st.file_uploader("File Ads")
        arev, aads = process_shopee_files(f1, f2)
    
    fr = arev if arev>0 else rev
    fa = aads if aads>0 else ads
    
    c1, c2, c3 = st.columns(3)
    nr = c1.number_input("Doanh thu", float(fr))
    na = c2.number_input("Chi phí Ads", float(fa))
    np = c3.number_input("Lợi nhuận", float(prof))
    if st.button("💾 LƯU BÁO CÁO"):
        save_weekly_metrics(d, nr, na, np)
        st.success("Đã đồng bộ Google Sheets!")

# ================= TAB 4: AI ASSISTANT =================
elif menu == "🤖 Trợ Lý AI":
    st.title("🤖 GEMINI STRATEGIST")
    if not client: st.error("Chưa nhập Key")
    else:
        df_c = get_competitors_df()
        info = df_c.to_string() if not df_c.empty else "Chưa có dữ liệu đối thủ."
        if st.button("Phân tích chiến lược giá"):
            with st.spinner("Gemini đang soi..."):
                prompt = f"Phân tích bảng giá đối thủ: {info}. Cho lời khuyên định giá."
                res = client.models.generate_content(model=AI_MODEL_ID, contents=prompt)
                st.write(res.text)

# ================= TAB 5: KHO HÀNG =================
elif menu == "📦 Kho Hàng":
    st.title("📦 KHO ONLINE")
    df = get_data_frame()
    if not df.empty:
        st.dataframe(df[['name','selling_price','stock_quantity','alert_threshold']])
        with st.form("stk"):
            pid = st.selectbox("Chọn SP", df['id'], format_func=lambda x: df[df['id']==x]['name'].values[0])
            qty = st.number_input("Nhập/Xuất (+/-)", step=1)
            if st.form_submit_button("Cập nhật kho"):
                update_stock(pid, qty); st.rerun()
    else: st.warning("Kho trống")
