# ==========================================
# TOOL QUẢN TRỊ SHOPEE - BCM VERSION 2.2 (FINAL)
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
    # Bảng Sản phẩm
    c.execute('''CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    cost_price INTEGER,
                    selling_price INTEGER,
                    stock_quantity INTEGER DEFAULT 0,
                    alert_threshold INTEGER DEFAULT 5
                )''')
    # Bảng Tài chính (Lưu Doanh thu/Ads theo ngày)
    c.execute('''CREATE TABLE IF NOT EXISTS financials (
                    date TEXT PRIMARY KEY,
                    revenue INTEGER DEFAULT 0,
                    ad_spend INTEGER DEFAULT 0,
                    profit INTEGER DEFAULT 0
                )''')
    conn.commit()
    conn.close()

init_db()

# --- 2. CÁC HÀM XỬ LÝ ---
def save_daily_metrics(revenue, ads, profit):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO financials (date, revenue, ad_spend, profit) VALUES (?, ?, ?, ?)", 
              (today, revenue, ads, profit))
    conn.commit()
    conn.close()

def get_today_metrics():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT revenue, ad_spend, profit FROM financials WHERE date = ?", (today,))
    data = c.fetchone()
    conn.close()
    if data:
        return data # (revenue, ads, profit)
    else:
        return (0, 0, 0) # Mặc định là 0 nếu chưa nhập

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
st.set_page_config(page_title="BCM Command Center", page_icon="💎", layout="wide")
st.markdown("""<style>[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 700; }</style>""", unsafe_allow_html=True)

st.sidebar.title("BCM v2.2")
st.sidebar.caption(f"📅 {datetime.now().strftime('%d/%m/%Y')}")
menu = st.sidebar.radio("Menu:", ["📊 Dashboard & Nhập Liệu", "💰 Tính Lãi & Niêm Yết", "📦 Quản Lý Kho Hàng"])

# ==================================================
# TAB 1: DASHBOARD (CÓ Ô NHẬP LIỆU)
# ==================================================
if menu == "📊 Dashboard & Nhập Liệu":
    st.title("👋 Chào Sếp Lâm!")
    
    # === KHU VỰC NHẬP LIỆU ===
    with st.expander("📝 CẬP NHẬT SỐ LIỆU HÔM NAY (Bấm vào đây để nhập)", expanded=True):
        st.caption("Nhập số liệu từ Shopee vào đây để App tính toán:")
        
        # Lấy số cũ ra (nếu có)
        cur_rev, cur_ads, cur_prof = get_today_metrics()
        
        c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
        with c1:
            in_rev = st.number_input("Tổng Doanh Thu", value=int(cur_rev), step=100000)
        with c2:
            in_ads = st.number_input("Chi Phí Ads", value=int(cur_ads), step=50000)
        with c3:
            in_prof = st.number_input("Lợi Nhuận Ròng", value=int(cur_prof), step=50000)
        with c4:
            st.write("") # Căn chỉnh nút bấm xuống dưới
            st.write("")
            if st.button("💾 LƯU LẠI", type="primary"):
                save_daily_metrics(in_rev, in_ads, in_prof)
                st.toast("Đã lưu dữ liệu thành công!", icon="✅")
                st.rerun() # Load lại trang ngay lập tức

    st.divider()

    # === KHU VỰC HIỂN THỊ (DASHBOARD) ===
    # Lấy dữ liệu thật vừa lưu
    real_rev, real_ads, real_prof = get_today_metrics()
    
    # Mục tiêu giả định (Sếp có thể sửa code này)
    TARGET_PROFIT = 5000000 
    
    c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
    
    with c_kpi1:
        delta = real_prof - TARGET_PROFIT
        st.metric("💰 LỢI NHUẬN", f"{real_prof:,.0f} đ", f"{delta:,.0f} đ (vs Mục tiêu)", delta_color="normal")
        
    with c_kpi2:
        cir = (real_ads / real_rev * 100) if real_rev > 0 else 0
        st.metric("🛒 DOANH THU", f"{real_rev:,.0f} đ", f"CIR Ads: {cir:.1f}%")
        
    with c_kpi3:
        lbl = "Ổn"
        if cir > 15: lbl = "Cao (Cắt giảm ngay)"
        elif cir < 8 and real_rev > 0: lbl = "Rất Tốt"
        st.metric("💸 CHI PHÍ ADS", f"{real_ads:,.0f} đ", lbl, delta_color="inverse")

    # === CẢNH BÁO KHO ===
    st.divider()
    st.subheader("🚨 Cảnh Báo Kho Hàng")
    df = get_data_frame()
    if not df.empty:
        critical = df[df['stock_quantity'] <= df['alert_threshold']]
        if critical.empty:
            st.success("✅ Kho hàng ổn định.")
        else:
            for idx, row in critical.iterrows():
                with st.container(border=True):
                    cols = st.columns([4, 1])
                    cols[0].markdown(f"**{row['name']}** - Còn: :red[{row['stock_quantity']}]")
                    cols[1].button("Nhập", key=f"alert_{row['id']}")
    else:
        st.info("Chưa có dữ liệu kho (Sang Tab Tính Lãi để thêm sản phẩm).")

# ==================================================
# TAB 2 & 3: GIỮ NGUYÊN
# ==================================================
elif menu == "💰 Tính Lãi & Niêm Yết":
    st.title("💰 TÍNH LÃI")
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
