# ==========================================
# TOOL QUẢN TRỊ SHOPEE - BCM VERSION 2.5 (SYSTEM THINKING)
# Coder: BCM-Engineer & Sếp Lâm
# Tư duy: Donella Meadows (Stocks & Flows)
# ==========================================

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# --- 1. CẤU HÌNH DATABASE & MIGRATION ---
DB_FILE = "shopee_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Tạo bảng Products (Nếu chưa có)
    c.execute('''CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    cost_price INTEGER,
                    selling_price INTEGER,
                    stock_quantity INTEGER DEFAULT 0,
                    alert_threshold INTEGER DEFAULT 5,
                    daily_sales REAL DEFAULT 1.0,  -- Tốc độ bán (Cái/ngày)
                    lead_time INTEGER DEFAULT 15,  -- Thời gian hàng về (Ngày)
                    safety_stock INTEGER DEFAULT 5 -- Tồn kho an toàn (Cái)
                )''')
    
    # Tạo bảng Financials
    c.execute('''CREATE TABLE IF NOT EXISTS financials (
                    date TEXT PRIMARY KEY,
                    revenue INTEGER DEFAULT 0,
                    ad_spend INTEGER DEFAULT 0,
                    profit INTEGER DEFAULT 0
                )''')
    
    # --- MIGRATION: Tự động thêm cột mới nếu Sếp đang dùng DB cũ ---
    try:
        c.execute("ALTER TABLE products ADD COLUMN daily_sales REAL DEFAULT 1.0")
    except: pass
    try:
        c.execute("ALTER TABLE products ADD COLUMN lead_time INTEGER DEFAULT 15")
    except: pass
    try:
        c.execute("ALTER TABLE products ADD COLUMN safety_stock INTEGER DEFAULT 5")
    except: pass

    conn.commit()
    conn.close()

init_db()

# --- 2. LOGIC HỆ THỐNG (SYSTEM LOGIC) ---

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

# Hàm nhập sản phẩm mới (Có thêm tham số hệ thống)
def add_product_to_db(name, cost, price, daily_sales, lead_time, safety):
    # Tính điểm báo động động (Dynamic Threshold)
    threshold = int(daily_sales * lead_time + safety)
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""INSERT INTO products 
                 (name, cost_price, selling_price, daily_sales, lead_time, safety_stock, alert_threshold) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)""", 
              (name, cost, price, daily_sales, lead_time, safety, threshold))
    conn.commit()
    conn.close()

def update_stock(product_id, amount):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (amount, product_id))
    conn.commit()
    conn.close()

# Hàm cập nhật thông số hệ thống (Sửa sản phẩm)
def update_product_system(product_id, daily_sales, lead_time, safety):
    threshold = int(daily_sales * lead_time + safety)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""UPDATE products 
                 SET daily_sales=?, lead_time=?, safety_stock=?, alert_threshold=? 
                 WHERE id=?""", 
              (daily_sales, lead_time, safety, threshold, product_id))
    conn.commit()
    conn.close()

def get_data_frame():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()
    return df

# Hàm đọc file Excel (Giữ nguyên từ v2.4)
def process_shopee_files(revenue_file, ads_file):
    total_revenue = 0
    total_ads = 0
    if revenue_file:
        try:
            if revenue_file.name.endswith('.csv'): df_rev = pd.read_csv(revenue_file)
            else: df_rev = pd.read_excel(revenue_file)
            possible_cols = [col for col in df_rev.columns if "thành tiền" in str(col).lower() or "tổng tiền" in str(col).lower()]
            if possible_cols:
                target_col = possible_cols[0]
                df_rev[target_col] = pd.to_numeric(df_rev[target_col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
                total_revenue = df_rev[target_col].sum()
                st.toast(f"✅ Đã đọc Doanh thu: {total_revenue:,.0f} đ", icon="💰")
        except: pass
    if ads_file:
        try:
            if ads_file.name.endswith('.csv'): df_ads = pd.read_csv(ads_file)
            else: df_ads = pd.read_excel(ads_file)
            possible_cols = [col for col in df_ads.columns if "chi phí" in str(col).lower()]
            if possible_cols:
                target_col = possible_cols[0]
                df_ads[target_col] = pd.to_numeric(df_ads[target_col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
                total_ads = df_ads[target_col].sum()
                st.toast(f"✅ Đã đọc Ads: {total_ads:,.0f} đ", icon="💸")
        except: pass
    return total_revenue, total_ads

# --- 3. GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="BCM System Thinking", page_icon="🧠", layout="wide")
st.markdown("""<style>[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 700; }</style>""", unsafe_allow_html=True)

st.sidebar.title("BCM v2.5 (System)")
menu = st.sidebar.radio("Menu:", ["📊 Báo Cáo & Nhập Liệu", "💰 Tính Lãi & Thêm Mới", "📦 Kho & Dòng Chảy"])

# ==================================================
# TAB 1: DASHBOARD (GIỮ NGUYÊN + CẬP NHẬT KHO THÔNG MINH)
# ==================================================
if menu == "📊 Báo Cáo & Nhập Liệu":
    st.title("🧠 TRUNG TÂM CHỈ HUY (SYSTEM MODE)")

    # --- CHỌN TUẦN & UPLOAD ---
    c_date, c_upload = st.columns([1, 2])
    with c_date:
        pick_date = st.date_input("Chọn tuần:", datetime.now())
    with c_upload:
        with st.expander("📂 Upload File Shopee (Tự động tính)", expanded=False):
            rev_file = st.file_uploader("File Doanh thu", type=['xlsx','csv'])
            ads_file = st.file_uploader("File Quảng cáo", type=['xlsx','csv'])
            auto_rev, auto_ads = process_shopee_files(rev_file, ads_file)

    # --- FORM LƯU ---
    cur_rev, cur_ads, cur_prof = get_weekly_metrics(pick_date)
    final_rev = auto_rev if auto_rev > 0 else cur_rev
    final_ads = auto_ads if auto_ads > 0 else cur_ads
    
    with st.container(border=True):
        st.subheader("📝 Chốt Sổ Tuần")
        c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
        with c1: in_rev = st.number_input("Doanh Thu", value=float(final_rev), step=1e6)
        with c2: in_ads = st.number_input("Tiền Ads", value=float(final_ads), step=5e5)
        with c3: in_prof = st.number_input("Lợi Nhuận", value=float(cur_prof), step=5e5)
        with c4: 
            st.write(""); st.write("")
            if st.button("💾 LƯU", type="primary"):
                save_weekly_metrics(pick_date, in_rev, in_ads, in_prof)
                st.rerun()
    
    # --- KPI ---
    st.divider()
    TARGET = 30000000
    c_k1, c_k2, c_k3 = st.columns(3)
    c_k1.metric("LỢI NHUẬN", f"{in_prof:,.0f} đ", f"{in_prof-TARGET:,.0f} đ")
    cir = (in_ads/in_rev*100) if in_rev>0 else 0
    c_k2.metric("DOANH THU", f"{in_rev:,.0f} đ", f"CIR: {cir:.1f}%")
    lbl_ads = "Tốt" if cir < 10 else "Cao"
    c_k3.metric("CHI PHÍ ADS", f"{in_ads:,.0f} đ", lbl_ads, delta_color="inverse")

    # --- CẢNH BÁO NHẬP HÀNG (THÔNG MINH) ---
    st.divider()
    st.subheader("🚨 Cảnh Báo Nhập Hàng (Theo Dòng Chảy)")
    df = get_data_frame()
    if not df.empty:
        # Tính lại ngưỡng báo động nếu user có sửa đổi
        # Logic: Threshold = (Daily Sales * Lead Time) + Safety
        df['system_threshold'] = (df['daily_sales'] * df['lead_time']) + df['safety_stock']
        
        # Lọc những mã dưới ngưỡng
        critical = df[df['stock_quantity'] <= df['system_threshold']]
        
        if critical.empty:
            st.success("✅ Hệ thống ổn định. Dòng chảy hàng hóa an toàn.")
        else:
            for idx, row in critical.iterrows():
                with st.container(border=True):
                    c_img, c_txt, c_act = st.columns([1, 5, 2])
                    with c_txt:
                        st.markdown(f"**{row['name']}**")
                        # Tính số ngày còn lại
                        days_left = int(row['stock_quantity'] / row['daily_sales']) if row['daily_sales'] > 0 else 999
                        st.caption(f"Kho: :red[{row['stock_quantity']}] | Tốc độ bán: **{row['daily_sales']}**/ngày | Còn trụ được: **{days_left} ngày**")
                        st.caption(f"⚠️ Điểm đặt hàng (ROP): **{int(row['system_threshold'])}** (Do ship mất {row['lead_time']} ngày)")
                    with c_act:
                        st.button("Nhập Ngay 📦", key=f"alert_{row['id']}")
    else:
        st.info("Chưa có dữ liệu kho.")

# ==================================================
# TAB 2: TÍNH LÃI (CÓ THÊM THAM SỐ HỆ THỐNG)
# ==================================================
elif menu == "💰 Tính Lãi & Thêm Mới":
    st.title("💰 CÔNG CỤ TÍNH LÃI & NIÊM YẾT")
    st.info("💡 Mẹo: Nhập 'Tốc độ bán' và 'Thời gian ship' để App tính điểm rơi nhập hàng chuẩn xác.")

    c1, c2 = st.columns(2)
    with c1:
        ten = st.text_input("Tên SP")
        von = st.number_input("Giá Vốn", step=1000)
        daily = st.number_input("Tốc độ bán dự kiến (Cái/ngày)", value=1.0, step=0.5)
    with c2:
        ban = st.number_input("Giá Bán", step=1000)
        lead = st.number_input("Thời gian hàng về (Ngày)", value=15, step=1)
        safety = st.number_input("Tồn an toàn (Cái)", value=5, step=1)
    
    hop = 2000
    san = 0.16
    
    if st.button("🚀 TÍNH TOÁN", type="primary"):
        lai = ban - (ban*san) - von - hop
        rop = int(daily * lead + safety) # Reorder Point
        
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("Lãi Ròng", f"{lai:,.0f} đ", f"{(lai/ban*100) if ban>0 else 0:.1f}%")
        m2.metric("Điểm Đặt Hàng (ROP)", f"{rop} cái", "Ngưỡng báo động")
        m3.metric("Vòng quay vốn", f"~{int(rop/daily)} ngày", "Chu kỳ nhập")

        if lai > 0:
            if st.button("💾 LƯU VÀO HỆ THỐNG"):
                add_product_to_db(ten, von, ban, daily, lead, safety)
                st.success(f"Đã lưu! Hệ thống sẽ báo động khi kho dưới {rop} cái.")

# ==================================================
# TAB 3: KHO & DÒNG CHẢY (QUẢN LÝ THÔNG SỐ)
# ==================================================
elif menu == "📦 Kho & Dòng Chảy":
    st.title("📦 QUẢN TRỊ KHO & DÒNG CHẢY")
    
    df = get_data_frame()
    if not df.empty:
        # Hiển thị bảng tổng quan
        st.dataframe(
            df[['name', 'stock_quantity', 'daily_sales', 'lead_time', 'alert_threshold']], 
            column_config={
                "name": "Tên SP",
                "stock_quantity": "Tồn kho",
                "daily_sales": "Bán/Ngày",
                "lead_time": "Ship (Ngày)",
                "alert_threshold": "Ngưỡng Báo"
            },
            use_container_width=True
        )

        st.divider()
        
        c_left, c_right = st.columns(2)
        
        # 1. CẬP NHẬT SỐ LƯỢNG (NHẬP/XUẤT)
        with c_left:
            st.subheader("🛠️ Nhập/Xuất Kho")
            with st.form("update_qty"):
                pid = st.selectbox("Chọn SP", df['id'], format_func=lambda x: df[df['id']==x]['name'].values[0])
                qty = st.number_input("Số lượng (+/-)", step=1)
                if st.form_submit_button("Cập nhật Tồn Kho"):
                    update_stock(pid, qty)
                    st.toast("Đã cập nhật!")
                    st.rerun()

        # 2. CẬP NHẬT THÔNG SỐ HỆ THỐNG (TƯ DUY)
        with c_right:
            st.subheader("🧠 Chỉnh Thông Số Hệ Thống")
            st.caption("Điều chỉnh khi Tốc độ bán hoặc Thời gian ship thay đổi.")
            
            # Chọn SP để sửa
            selected_id_sys = st.selectbox("Chọn SP để chỉnh:", df['id'], key="sys_select", format_func=lambda x: df[df['id']==x]['name'].values[0])
            
            # Lấy thông tin hiện tại
            curr_row = df[df['id'] == selected_id_sys].iloc[0]
            
            with st.form("update_sys"):
                new_daily = st.number_input("Tốc độ bán (Cái/ngày)", value=float(curr_row['daily_sales']), step=0.1)
                new_lead = st.number_input("Thời gian ship (Ngày)", value=int(curr_row['lead_time']), step=1)
                new_safety = st.number_input("Tồn an toàn", value=int(curr_row['safety_stock']), step=1)
                
                # Tính trước ROP mới để user thấy
                new_rop = int(new_daily * new_lead + new_safety)
                st.markdown(f"👉 **Ngưỡng báo động mới sẽ là: {new_rop} cái**")
                
                if st.form_submit_button("Lưu Thông Số Mới"):
                    update_product_system(selected_id_sys, new_daily, new_lead, new_safety)
                    st.success("Đã cập nhật tư duy hệ thống cho sản phẩm này!")
                    st.rerun()

    else:
        st.warning("Kho trống.")
