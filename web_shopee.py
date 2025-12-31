# ==========================================
# TOOL QUẢN TRỊ SHOPEE - BCM VERSION 2.1 (FULL TÍNH NĂNG)
# Coder: BCM-Engineer & Sếp Lâm
# ==========================================

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

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
    conn.commit()
    conn.close()

# Khởi tạo DB ngay khi chạy
init_db()

# --- 2. CÁC HÀM XỬ LÝ DỮ LIỆU ---
def add_product_to_db(name, cost, price):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO products (name, cost_price, selling_price) VALUES (?, ?, ?)", 
              (name, cost, price))
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
st.set_page_config(page_title="BCM Command Center", page_icon="💎", layout="wide")

# CSS làm đẹp giao diện
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 700; }
    div.stButton > button { width: 100%; border-radius: 8px; }
    .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# SIDEBAR MENU
st.sidebar.title("BCM v2.0")
st.sidebar.caption(f"📅 {datetime.now().strftime('%d/%m/%Y')}")
menu = st.sidebar.radio("Menu:", ["📊 Dashboard Chỉ Huy", "💰 Tính Lãi & Niêm Yết", "📦 Quản Lý Kho Hàng"])

# ==================================================
# TAB 1: DASHBOARD CHỈ HUY (Storytelling)
# ==================================================
if menu == "📊 Dashboard Chỉ Huy":
    st.title("👋 Chào Sếp Lâm! Báo cáo nhanh")
    
    # 1. BIG NUMBERS
    TARGET_PROFIT = 5000000
    current_profit = 4200000 
    current_revenue = 15500000
    ad_spend = 1200000
    profit_delta = current_profit - TARGET_PROFIT

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("💰 LỢI NHUẬN RÒNG", f"{current_profit:,.0f} đ", f"{profit_delta:,.0f} đ vs Mục tiêu", delta_color="normal")
    with c2:
        st.metric("🛒 DOANH THU", f"{current_revenue:,.0f} đ", "Tăng trưởng")
    with c3:
        st.metric("💸 CHI PHÍ ADS", f"{ad_spend:,.0f} đ", "-10%", delta_color="inverse")

    st.divider()

    # 2. ACTION CENTER
    col_stock, col_ads = st.columns(2)

    with col_stock:
        st.subheader("🚨 Kho Hàng Báo Động")
        df = get_data_frame()
        if not df.empty:
            critical_items = df[df['stock_quantity'] <= df['alert_threshold']]
            if critical_items.empty:
                st.success("✅ Kho hàng ổn định.")
            else:
                for idx, row in critical_items.iterrows():
                    with st.container(border=True):
                        c_text, c_btn = st.columns([3, 1])
                        with c_text:
                            st.markdown(f"**{row['name']}**")
                            if row['stock_quantity'] == 0:
                                st.caption(":red[HẾT HÀNG (0)]")
                            else:
                                st.caption(f":orange[Sắp hết: {row['stock_quantity']}]")
                        with c_btn:
                            st.button("Nhập", key=f"stock_{row['id']}")
        else:
            st.info("Chưa có dữ liệu kho.")

    with col_ads:
        st.subheader("📉 Ads Kém Hiệu Quả")
        st.success("✅ Ads đang chạy ngon (Demo).")

# ==================================================
# TAB 2: TÍNH LÃI & THÊM MỚI (Đã phục hồi code cũ)
# ==================================================
elif menu == "💰 Tính Lãi & Niêm Yết":
    st.title("💰 CÔNG CỤ TÍNH LÃI")
    st.write("Nhập thông tin để tính lãi và lưu vào kho.")

    col1, col2 = st.columns(2)
    with col1:
        ten_sp = st.text_input("Tên sản phẩm", placeholder="Ví dụ: Chổi X40 Tricut")
        gia_nhap = st.number_input("Giá nhập (Vốn)", min_value=0, step=1000, format="%d")
    with col2:
        gia_ban = st.number_input("Giá bán niêm yết", min_value=0, step=1000, format="%d")
        dong_goi = st.number_input("Chi phí đóng gói", value=2000, step=500, format="%d")

    phi_san_percent = st.slider("Phí sàn Shopee (%)", 10, 25, 16) / 100

    if st.button("🚀 TÍNH LÃI NGAY", type="primary"):
        tien_phi_san = gia_ban * phi_san_percent
        doanh_thu_thuc = gia_ban - tien_phi_san
        lai_rong = doanh_thu_thuc - gia_nhap - dong_goi
        ty_suat = (lai_rong / gia_ban * 100) if gia_ban > 0 else 0

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Sàn thu", f"{tien_phi_san:,.0f} đ")
        c2.metric("Vốn + Hộp", f"{gia_nhap + dong_goi:,.0f} đ")
        c3.metric("LÃI RÒNG", f"{lai_rong:,.0f} đ", delta=f"{ty_suat:.1f}%")

        if lai_rong > 0:
            st.success("✅ Kèo thơm! Có thể nhập kho.")
            if st.button("💾 LƯU VÀO KHO"):
                add_product_to_db(ten_sp, gia_nhap, gia_ban)
                st.toast(f"Đã lưu '{ten_sp}' vào hệ thống!", icon="🎉")
        else:
            st.error("❌ Lỗ hoặc lãi quá mỏng! Xem lại giá.")

# ==================================================
# TAB 3: QUẢN LÝ KHO (Đã phục hồi code cũ)
# ==================================================
elif menu == "📦 Quản Lý Kho Hàng":
    st.title("📦 KHO HÀNG")
    
    df = get_data_frame()

    if df.empty:
        st.warning("Kho đang trống. Hãy sang tab 'Tính Lãi' để thêm hàng!")
    else:
        # Cập nhật nhanh
        st.subheader("🛠️ Cập Nhật Tồn Kho")
        c1, c2, c3 = st.columns([3, 2, 2])
        
        with c1:
            product_options = df.set_index('id')['name'].to_dict()
            selected_id = st.selectbox("Chọn sản phẩm:", options=list(product_options.keys()), format_func=lambda x: product_options[x])
        with c2:
            qty_change = st.number_input("Số lượng (+/-)", step=1, value=0)
        with c3:
            st.write("")
            st.write("")
            if st.button("Cập nhật"):
                if qty_change != 0:
                    update_stock(selected_id, qty_change)
                    st.toast("Đã cập nhật!", icon="✅")
                    st.rerun()

        st.divider()
        st.subheader("📋 Danh Sách Chi Tiết")
        st.dataframe(df[['name', 'stock_quantity', 'selling_price']], use_container_width=True)
