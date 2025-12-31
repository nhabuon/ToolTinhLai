# ==========================================
# TOOL QUẢN TRỊ SHOPEE - BCM VERSION 2.2 (CÓ DỮ LIỆU THỰC)
# Coder: BCM-Engineer & Sếp Lâm
# ==========================================

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. CẤU HÌNH DATABASE (Update thêm bảng Tài chính) ---
DB_FILE = "shopee_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Bảng Sản phẩm (Kho)
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

# --- 2. CÁC HÀM XỬ LÝ DỮ LIỆU ---
def save_daily_metrics(revenue, ads, profit):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Dùng REPLACE để nếu nhập lại trong ngày thì nó cập nhật số mới
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
        return (0, 0, 0) # Chưa nhập thì trả về 0

# Các hàm cũ giữ nguyên
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

# SIDEBAR
st.sidebar.title("BCM v2.2")
st.sidebar.caption(f"📅 {datetime.now().strftime('%d/%m/%Y')}")
menu = st.sidebar.radio("Menu:", ["📊 Dashboard & Nhập Liệu", "💰 Tính Lãi & Niêm Yết", "📦 Quản Lý Kho Hàng"])

# ==================================================
# TAB 1: DASHBOARD (ĐÃ CÓ CHỖ NHẬP LIỆU)
# ==================================================
if menu == "📊 Dashboard & Nhập Liệu":
    st.title("👋 Chào Sếp Lâm!")
    
    # --- KHU VỰC 1: NHẬP SỐ LIỆU HÔM NAY ---
    with st.expander("📝 CẬP NHẬT SỐ LIỆU HÔM NAY (Mở ra để nhập)", expanded=True):
        st.caption("Sếp mở App Shopee -> Xem 'Phân tích bán hàng' -> Nhập 3 số vào đây:")
        c_in1, c_in2, c_in3, c_btn = st.columns([2, 2, 2, 1])
        
        # Lấy dữ liệu cũ nếu đã nhập
        cur_rev, cur_ads, cur_prof = get_today_metrics()
        
        with c_in1:
            in_rev = st.number_input("Tổng Doanh Thu", value=cur_rev, step=100000)
        with c_in2:
            in_ads = st.number_input("Chi Phí Ads", value=cur_ads, step=50000)
        with c_in3:
            in_prof = st.number_input("Lợi Nhuận (Ước tính)", value=cur_prof, step=50000)
        with c_btn:
            st.write("") # Spacer
            st.write("") 
            if st.button("Lưu lại 💾", type="primary"):
                save_daily_metrics(in_rev, in_ads, in_prof)
                st.toast("Đã lưu dữ liệu ngày hôm nay!", icon="✅")
                st.rerun()

    st.divider()

    # --- KHU VỰC 2: HIỂN THỊ DASHBOARD (DỮ LIỆU THẬT) ---
    # Lấy lại dữ liệu mới nhất
    real_rev, real_ads, real_prof = get_today_metrics()
    TARGET_PROFIT = 5000000 # Mục tiêu ngày
    
    c1, c2, c3 = st.columns(3)
    with c1:
        delta_prof = real_prof - TARGET_PROFIT
        st.metric("💰 LỢI NHUẬN RÒNG", f"{real_prof:,.0f} đ", f"{delta_prof:,.0f} đ (Mục tiêu)", delta_color="normal")
    with c2:
        # Tính % Chi phí Ads / Doanh thu (CIR)
        cir = (real_ads / real_rev * 100) if real_rev > 0 else 0
        st.metric("🛒 DOANH THU", f"{real_rev:,.0f} đ", f"CIR Ads: {cir:.1f}%")
    with c3:
        # Đánh giá Ads
        lbl_ads = "Bình thường"
        if cir > 15: lbl_ads = "Cao (Nguy hiểm)"
        elif cir < 8 and real_rev > 0: lbl_ads = "Tốt (Rẻ)"
        st.metric("💸 CHI PHÍ ADS", f"{real_ads:,.0f} đ", lbl_ads, delta_color="inverse")

    # --- KHU VỰC 3: CẢNH BÁO KHO (GIỮ NGUYÊN) ---
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
        st.info("Chưa có dữ liệu kho.")

# ==================================================
# TAB 2: TÍNH LÃI (GIỮ NGUYÊN)
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
    
    if st.button("Tính Lãi", type="primary"):
        phi = ban * san
        lai = ban - phi - von - hop
        st.metric("Lãi Ròng", f"{lai:,.0f} đ", f"{(lai/ban*100) if ban>0 else 0:.1f}%")
        if lai > 0 and st.button("Lưu Kho"):
            add_product_to_db(ten, von, ban)
            st.success("Đã lưu!")

# ==================================================
# TAB 3: KHO HÀNG (GIỮ NGUYÊN)
# ==================================================
elif menu == "📦 Quản Lý Kho Hàng":
    st.title("📦 KHO HÀNG")
    df = get_data_frame()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        # Form cập nhật nhanh
        with st.form("update_stock"):
            c1, c2 = st.columns([3, 1])
            pid = c1.selectbox("Chọn SP", df['id'], format_func=lambda x: df[df['id']==x]['name'].values[0])
            qty = c2.number_input("Số lượng (+/-)", step=1)
            if st.form_submit_button("Cập nhật"):
                update_stock(pid, qty)
                st.rerun()
    else:
        st.warning("Kho trống.")
