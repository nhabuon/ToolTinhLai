# ==========================================
# TOOL QUẢN TRỊ SHOPEE - BCM VERSION 2.9 (FULL OPTIONS)
# Coder: BCM-Engineer & Sếp Lâm
# Update: Khôi phục tính năng Tính Lãi chi tiết + AI Gemini 3.0
# ==========================================

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from google import genai # Thư viện AI chuẩn mới 2026

# --- CẤU HÌNH AI ---
AI_MODEL_ID = 'gemini-2.0-flash-exp' # Hoặc 'gemini-1.5-pro' tùy key của Sếp

# --- 1. CẤU HÌNH DATABASE ---
DB_FILE = "shopee_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    cost_price INTEGER,
                    selling_price INTEGER,
                    stock_quantity INTEGER DEFAULT 0,
                    alert_threshold INTEGER DEFAULT 5,
                    daily_sales REAL DEFAULT 1.0,
                    lead_time INTEGER DEFAULT 15,
                    safety_stock INTEGER DEFAULT 5
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS financials (
                    date TEXT PRIMARY KEY,
                    revenue INTEGER DEFAULT 0,
                    ad_spend INTEGER DEFAULT 0,
                    profit INTEGER DEFAULT 0
                )''')
    conn.commit()
    conn.close()

init_db()

# --- 2. CÁC HÀM XỬ LÝ SỐ LIỆU ---
def get_start_of_week(date_obj):
    return date_obj - timedelta(days=date_obj.weekday())

def save_weekly_metrics(selected_date, revenue, ads, profit):
    start_date = get_start_of_week(selected_date).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO financials (date, revenue, ad_spend, profit) VALUES (?, ?, ?, ?)", 
              (start_date, revenue, ads, profit))
    conn.commit()
    conn.close()

def get_weekly_metrics(selected_date):
    start_date = get_start_of_week(selected_date).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT revenue, ad_spend, profit FROM financials WHERE date = ?", (start_date,))
    data = c.fetchone()
    conn.close()
    return data if data else (0, 0, 0)

def add_product_to_db(name, cost, price, daily_sales, lead_time, safety):
    threshold = int(daily_sales * lead_time + safety)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""INSERT INTO products (name, cost_price, selling_price, daily_sales, lead_time, safety_stock, alert_threshold) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)""", (name, cost, price, daily_sales, lead_time, safety, threshold))
    conn.commit()
    conn.close()

def update_stock(product_id, amount):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (amount, product_id))
    conn.commit()
    conn.close()

def get_data_frame():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()
    return df

def process_shopee_files(revenue_file, ads_file):
    total_revenue = 0
    total_ads = 0
    if revenue_file:
        try:
            if revenue_file.name.endswith('.csv'): df_rev = pd.read_csv(revenue_file)
            else: df_rev = pd.read_excel(revenue_file)
            possible_cols = [col for col in df_rev.columns if "thành tiền" in str(col).lower() or "tổng tiền" in str(col).lower()]
            if possible_cols:
                target = possible_cols[0]
                df_rev[target] = pd.to_numeric(df_rev[target].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
                total_revenue = df_rev[target].sum()
        except: pass
    if ads_file:
        try:
            if ads_file.name.endswith('.csv'): df_ads = pd.read_csv(ads_file)
            else: df_ads = pd.read_excel(ads_file)
            possible_cols = [col for col in df_ads.columns if "chi phí" in str(col).lower()]
            if possible_cols:
                target = possible_cols[0]
                df_ads[target] = pd.to_numeric(df_ads[target].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
                total_ads = df_ads[target].sum()
        except: pass
    return total_revenue, total_ads

# --- 3. GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="BCM AI Pro", page_icon="💎", layout="wide")
st.markdown("""<style>[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 700; }</style>""", unsafe_allow_html=True)

# SIDEBAR
st.sidebar.title("BCM v2.9 (Full Option)")
api_key = st.sidebar.text_input("🔑 Google API Key:", type="password")
client = None
if api_key:
    try:
        client = genai.Client(api_key=api_key)
        st.sidebar.success(f"AI đã sẵn sàng! 🟢")
    except: st.sidebar.error("Lỗi Key")

menu = st.sidebar.radio("Menu:", ["💰 Tính Lãi & Thêm Mới", "🤖 Trợ Lý AI (Gemini)", "📊 Báo Cáo & Nhập Liệu", "📦 Kho & Dòng Chảy"])

# ==================================================
# TAB 1: TÍNH LÃI (ĐÃ KHÔI PHỤC FULL TÍNH NĂNG)
# ==================================================
if menu == "💰 Tính Lãi & Thêm Mới":
    st.title("💰 CÔNG CỤ TÍNH LÃI (CHI TIẾT)")
    st.info("💡 Nhập đầy đủ thông tin để tính ra Lãi Ròng chính xác nhất.")

    # KHU VỰC NHẬP LIỆU
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            ten = st.text_input("Tên sản phẩm", placeholder="VD: Con lăn H13")
            von = st.number_input("Giá Vốn (VNĐ)", step=1000, format="%d")
        with c2:
            ban = st.number_input("Giá Bán (VNĐ)", step=1000, format="%d")
            hop = st.number_input("Phí đóng gói (Hộp/Băng dính)", value=2000, step=500)
        with c3:
            daily = st.number_input("Tốc độ bán (Cái/ngày)", value=1.0)
            lead = st.number_input("Thời gian ship (Ngày)", value=15)
            safety = st.number_input("Tồn an toàn", value=5)
        
        # SLIDER PHÍ SÀN (QUAN TRỌNG)
        st.write("---")
        phi_san_percent = st.slider("Phí sàn Shopee + Voucher + Freeship (%)", 0, 25, 16)
        
        # NÚT TÍNH TOÁN
        if st.button("🚀 TÍNH LÃI NGAY", type="primary"):
            # Logic tính toán
            tien_phi_san = ban * (phi_san_percent / 100)
            doanh_thu_thuc = ban - tien_phi_san
            lai_rong = doanh_thu_thuc - von - hop
            ty_suat = (lai_rong / ban * 100) if ban > 0 else 0
            
            # Logic hệ thống (ROP)
            rop = int(daily * lead + safety)
            
            # Hiển thị kết quả
            st.divider()
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Sàn thu", f"{tien_phi_san:,.0f} đ", f"-{phi_san_percent}%")
            m2.metric("Vốn + Gói", f"{von + hop:,.0f} đ")
            m3.metric("LÃI RÒNG", f"{lai_rong:,.0f} đ", f"Margin: {ty_suat:.1f}%", delta_color="normal" if lai_rong > 0 else "inverse")
            m4.metric("Điểm nhập hàng", f"{rop} cái", "Báo động")
            
            # Nút Lưu (Chỉ hiện khi đã tính xong)
            if lai_rong > 0:
                st.success("✅ Kèo này ổn! Có thể kinh doanh.")
                if st.button("💾 LƯU VÀO HỆ THỐNG"):
                    add_product_to_db(ten, von, ban, daily, lead, safety)
                    st.toast("Đã lưu thành công!", icon="🎉")
            else:
                st.error("❌ Lỗ hoặc lãi quá mỏng! Hãy tăng giá bán hoặc giảm giá nhập.")

# ==================================================
# TAB 2: TRỢ LÝ AI (GIỮ NGUYÊN)
# ==================================================
elif menu == "🤖 Trợ Lý AI (Gemini)":
    st.title("🤖 TRỢ LÝ CHIẾN LƯỢC")
    col_ai1, col_ai2 = st.columns(2)
    with col_ai1:
        with st.container(border=True):
            st.subheader("📊 Phân Tích Hiệu Quả")
            today = datetime.now()
            cur_rev, cur_ads, cur_prof = get_weekly_metrics(today)
            st.info(f"Doanh thu: {cur_rev:,.0f}đ | Ads: {cur_ads:,.0f}đ | Lãi: {cur_prof:,.0f}đ")
            if st.button("🚀 Phân Tích"):
                if not client: st.error("Chưa nhập Key")
                else:
                    with st.spinner("Đang suy nghĩ..."):
                        prompt = f"Phân tích hiệu quả Shopee tuần này. Doanh thu: {cur_rev}, Ads: {cur_ads}, Lãi: {cur_prof}. Ngắn gọn, súc tích."
                        try:
                            res = client.models.generate_content(model=AI_MODEL_ID, contents=prompt)
                            st.markdown(res.text)
                        except Exception as e: st.error(f"Lỗi: {e}")
    with col_ai2:
        with st.container(border=True):
            st.subheader("✍️ Viết Content")
            name = st.text_input("Tên SP")
            key = st.text_input("Từ khóa")
            if st.button("✨ Viết Bài"):
                if not client: st.error("Chưa nhập Key")
                else:
                    with st.spinner("Đang viết..."):
                        prompt = f"Viết mô tả Shopee cho {name}, từ khóa {key}. Có icon."
                        try:
                            res = client.models.generate_content(model=AI_MODEL_ID, contents=prompt)
                            st.text_area("Kết quả", res.text, height=300)
                        except Exception as e: st.error(f"Lỗi: {e}")

# ==================================================
# CÁC TAB CÒN LẠI (GIỮ NGUYÊN)
# ==================================================
elif menu == "📊 Báo Cáo & Nhập Liệu":
    st.title("📊 TRUNG TÂM CHỈ HUY")
    c_date, c_upload = st.columns([1, 2])
    with c_date: pick_date = st.date_input("Chọn tuần:", datetime.now())
    with c_upload: 
        with st.expander("Upload File Excel"):
            rev_file = st.file_uploader("Doanh thu")
            ads_file = st.file_uploader("Ads")
            auto_rev, auto_ads = process_shopee_files(rev_file, ads_file)
            
    cur_rev, cur_ads, cur_prof = get_weekly_metrics(pick_date)
    final_rev = auto_rev if auto_rev > 0 else cur_rev
    final_ads = auto_ads if auto_ads > 0 else cur_ads
    
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
        with c1: in_rev = st.number_input("Doanh Thu", value=float(final_rev), step=1e6)
        with c2: in_ads = st.number_input("Tiền Ads", value=float(final_ads), step=5e5)
        with c3: in_prof = st.number_input("Lợi Nhuận", value=float(cur_prof), step=5e5)
        with c4: 
            st.write(""); st.write("")
            if st.button("💾 LƯU"): save_weekly_metrics(pick_date, in_rev, in_ads, in_prof); st.rerun()

elif menu == "📦 Kho & Dòng Chảy":
    st.title("📦 KHO HÀNG")
    df = get_data_frame()
    if not df.empty:
        st.dataframe(df[['name', 'stock_quantity', 'alert_threshold']], use_container_width=True)
        with st.form("up"):
            pid = st.selectbox("SP", df['id'], format_func=lambda x: df[df['id']==x]['name'].values[0])
            qty = st.number_input("Số lượng", step=1)
            if st.form_submit_button("Cập nhật"): update_stock(pid, qty); st.rerun()
    else: st.warning("Kho trống")
