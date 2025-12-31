# ==========================================
# TOOL QUẢN TRỊ SHOPEE - BCM VERSION 2.4 (AUTO EXCEL IMPORT)
# Coder: BCM-Engineer & Sếp Lâm
# ==========================================

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

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
                    alert_threshold INTEGER DEFAULT 5
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

# --- 2. LOGIC XỬ LÝ SỐ LIỆU ---

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

# --- 🔥 HÀM THÔNG MINH: ĐỌC FILE EXCEL SHOPEE ---
def process_shopee_files(revenue_file, ads_file):
    total_revenue = 0
    total_ads = 0
    
    # 1. Xử lý File Doanh Thu
    if revenue_file:
        try:
            # Shopee thường xuất file CSV hoặc Excel. Ta dùng pandas đọc thử.
            if revenue_file.name.endswith('.csv'):
                df_rev = pd.read_csv(revenue_file)
            else:
                df_rev = pd.read_excel(revenue_file)
            
            # Logic tìm cột: Tìm cột nào có chữ "Thành tiền", "Doanh thu", "Total Amount"
            # Sếp cần check xem file Shopee cột tiền tên là gì. 
            # Ở đây An demo tìm cột chứa từ khóa thông dụng.
            possible_cols = [col for col in df_rev.columns if "thành tiền" in str(col).lower() or "tổng tiền" in str(col).lower() or "doanh thu" in str(col).lower()]
            
            if possible_cols:
                target_col = possible_cols[0] # Lấy cột đầu tiên tìm thấy
                # Chuyển đổi dữ liệu sang số (bỏ dấu phẩy, chữ đ)
                df_rev[target_col] = pd.to_numeric(df_rev[target_col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
                total_revenue = df_rev[target_col].sum()
                st.toast(f"✅ Đã đọc file Doanh thu: {total_revenue:,.0f} đ", icon="💰")
            else:
                st.warning("⚠️ Không tìm thấy cột 'Doanh thu/Tổng tiền' trong file. Vui lòng nhập tay.")
        except Exception as e:
            st.error(f"Lỗi đọc file Doanh thu: {e}")

    # 2. Xử lý File Quảng Cáo
    if ads_file:
        try:
            if ads_file.name.endswith('.csv'):
                df_ads = pd.read_csv(ads_file)
            else:
                df_ads = pd.read_excel(ads_file)
                
            # Tìm cột "Chi phí" hoặc "Expense"
            possible_cols = [col for col in df_ads.columns if "chi phí" in str(col).lower() or "expense" in str(col).lower()]
            
            if possible_cols:
                target_col = possible_cols[0]
                df_ads[target_col] = pd.to_numeric(df_ads[target_col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
                total_ads = df_ads[target_col].sum()
                st.toast(f"✅ Đã đọc file Quảng cáo: {total_ads:,.0f} đ", icon="💸")
            else:
                st.warning("⚠️ Không tìm thấy cột 'Chi phí' trong file Ads.")
        except Exception as e:
            st.error(f"Lỗi đọc file Ads: {e}")
            
    return total_revenue, total_ads

# (Các hàm database cũ giữ nguyên)
def add_product_to_db(name, cost, price):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO products (name, cost_price, selling_price) VALUES (?, ?, ?)", (name, cost, price))
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

# --- 3. GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="BCM Auto Manager", page_icon="🤖", layout="wide")
st.markdown("""<style>[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 700; }</style>""", unsafe_allow_html=True)

st.sidebar.title("BCM v2.4 (Auto Import)")
menu = st.sidebar.radio("Menu:", ["📊 Báo Cáo Tuần (Auto)", "💰 Tính Lãi & Niêm Yết", "📦 Quản Lý Kho Hàng"])

if menu == "📊 Báo Cáo Tuần (Auto)":
    st.title("🤖 BÁO CÁO TỰ ĐỘNG (FILE EXCEL)")

    # 1. CHỌN TUẦN
    c_date, c_info = st.columns([1, 3])
    with c_date:
        pick_date = st.date_input("Chọn tuần báo cáo:", datetime.now())
    start_week = get_start_of_week(pick_date)
    end_week = start_week + timedelta(days=6)
    with c_info:
        st.info(f"Tuần: **{start_week.strftime('%d/%m')} - {end_week.strftime('%d/%m')}**")

    # 2. KHU VỰC UPLOAD FILE (TỰ ĐỘNG)
    with st.expander("📂 UPLOAD FILE SHOPEE ĐỂ TỰ ĐỘNG TÍNH (Mới!)", expanded=True):
        st.caption("Tải file Excel từ Shopee về và ném vào đây. App sẽ tự cộng tiền.")
        col_up1, col_up2 = st.columns(2)
        with col_up1:
            rev_file = st.file_uploader("1. File Đơn hàng/Doanh thu", type=['xlsx', 'csv', 'xls'])
        with col_up2:
            ads_file = st.file_uploader("2. File Quảng cáo Shopee", type=['xlsx', 'csv', 'xls'])

        # Xử lý tự động khi có file
        auto_rev = 0
        auto_ads = 0
        if rev_file or ads_file:
            auto_rev, auto_ads = process_shopee_files(rev_file, ads_file)

    # 3. FORM XÁC NHẬN & LƯU
    st.write("---")
    st.subheader("📝 Xác Nhận Số Liệu")
    
    # Lấy dữ liệu cũ
    cur_rev, cur_ads, cur_prof = get_weekly_metrics(pick_date)
    
    # Nếu vừa upload file, dùng số liệu từ file. Nếu không, dùng số liệu cũ.
    final_rev = auto_rev if auto_rev > 0 else cur_rev
    final_ads = auto_ads if auto_ads > 0 else cur_ads
    
    # Form nhập
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
    with c1:
        in_rev = st.number_input("Doanh Thu", value=float(final_rev), step=1000000.0)
    with c2:
        in_ads = st.number_input("Tiền Ads", value=float(final_ads), step=500000.0)
    with c3:
        # Lợi nhuận = Doanh thu - Ads - Vốn (Sếp tự ước lượng hoặc nhập tay thêm)
        # Ở đây tạm để nhập tay vì chưa tính được giá vốn hàng bán chính xác từ file tổng
        in_prof = st.number_input("Lợi Nhuận Ròng", value=float(cur_prof), step=500000.0)
    with c4:
        st.write("")
        st.write("")
        if st.button("💾 LƯU SỔ", type="primary"):
            save_weekly_metrics(pick_date, in_rev, in_ads, in_prof)
            st.toast("Đã lưu dữ liệu tuần!", icon="✅")
            st.rerun()

    # DASHBOARD KPI
    st.divider()
    TARGET = 30000000 
    c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
    with c_kpi1:
        st.metric("💰 LỢI NHUẬN", f"{cur_prof:,.0f} đ", f"{cur_prof-TARGET:,.0f} đ")
    with c_kpi2:
        cir = (cur_ads / cur_rev * 100) if cur_rev > 0 else 0
        st.metric("🛒 DOANH THU", f"{cur_rev:,.0f} đ", f"CIR: {cir:.1f}%")
    with c_kpi3:
        st.metric("💸 ADS", f"{cur_ads:,.0f} đ", delta_color="inverse")

# (Phần Tab 2 & 3 giữ nguyên như cũ - Sếp có thể copy từ bản v2.3 hoặc để An paste nốt nếu cần)
elif menu == "💰 Tính Lãi & Niêm Yết":
    st.title("💰 CÔNG CỤ TÍNH LÃI")
    c1, c2 = st.columns(2)
    with c1:
        ten = st.text_input("Tên SP")
        von = st.number_input("Giá Vốn", step=1000)
    with c2:
        ban = st.number_input("Giá Bán", step=1000)
        hop = st.number_input("Phí đóng gói", value=2000)
    san = st.slider("Phí sàn %", 10, 25, 16) / 100
    if st.button("🚀 Tính Lãi", type="primary"):
        phi = ban * san
        lai = ban - phi - von - hop
        st.metric("Lãi Ròng", f"{lai:,.0f} đ", f"{(lai/ban*100) if ban>0 else 0:.1f}%")
        if lai > 0 and st.button("💾 Lưu Kho"):
            add_product_to_db(ten, von, ban)
            st.success("Đã lưu!")

elif menu == "📦 Quản Lý Kho Hàng":
    st.title("📦 KHO HÀNG")
    df = get_data_frame()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        with st.form("update_stock"):
            c1, c2 = st.columns([3, 1])
            pid = c1.selectbox("Chọn SP", df['id'], format_func=lambda x: df[df['id']==x]['name'].values[0])
            qty = c2.number_input("Số lượng (+/-)", step=1)
            if st.form_submit_button("Cập nhật"):
                update_stock(pid, qty)
                st.rerun()
    else:
        st.warning("Kho trống.")
