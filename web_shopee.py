# ==========================================
# TOOL QUẢN TRỊ SHOPEE - BCM VERSION 2.1 (Update Dashboard)
# Coder: BCM-Engineer & Sếp Lâm
# ==========================================

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- CẤU HÌNH DATABASE ---
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

init_db()

# --- CÁC HÀM XỬ LÝ ---
def get_data_frame():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()
    return df

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="BCM Command Center", page_icon="💎", layout="wide")

# CSS TÙY CHỈNH ĐỂ GIAO DIỆN SẠCH SẼ HƠN (Declutter)
st.markdown("""
<style>
    [data-testid="stMetricValue"] {
        font-size: 2.5rem !important;
        font-weight: 700;
    }
    div.stButton > button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

st.sidebar.title("BCM v2.0")
st.sidebar.caption(f"📅 {datetime.now().strftime('%d/%m/%Y')}")
# THÊM MENU DASHBOARD VÀO ĐẦU
menu = st.sidebar.radio("Menu:", ["📊 Dashboard Chỉ Huy", "💰 Tính Lãi & Niêm Yết", "📦 Quản Lý Kho Hàng"])

# ==================================================
# TAB 1: DASHBOARD CHỈ HUY (Storytelling with Data)
# ==================================================
if menu == "📊 Dashboard Chỉ Huy":
    st.title("👋 Chào Sếp Lâm! Báo cáo nhanh hôm nay")
    
    # 1. BIG NUMBERS (CÁC CON SỐ BIẾT NÓI)
    # Giả lập dữ liệu doanh thu (Sau này sẽ nối API Shopee thật)
    TARGET_PROFIT = 5000000
    current_profit = 4200000  # Ví dụ hôm nay lãi 4.2tr
    current_revenue = 15500000
    ad_spend = 1200000

    # Logic màu sắc (Delta)
    profit_delta = current_profit - TARGET_PROFIT # Nếu âm sẽ hiện đỏ, dương hiện xanh

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            label="💰 LỢI NHUẬN RÒNG (Hôm nay)", 
            value=f"{current_profit:,.0f} đ", 
            delta=f"{profit_delta:,.0f} đ so với mục tiêu",
            delta_color="normal" # Tự động xanh/đỏ
        )
    with c2:
        st.metric(label="🛒 TỔNG DOANH THU", value=f"{current_revenue:,.0f} đ", delta="Tăng trưởng")
    with c3:
        st.metric(label="💸 CHI PHÍ ADS", value=f"{ad_spend:,.0f} đ", delta="-10% (Tốt)", delta_color="inverse")

    st.divider()

    # 2. ACTION CENTER (KHU VỰC CẦN XỬ LÝ)
    # Tư duy: Chỉ hiện cái XẤU, cái TỐT ẩn đi
    
    col_stock, col_ads = st.columns(2)

    # --- CỘT TRÁI: CẢNH BÁO KHO ---
    with col_stock:
        st.subheader("🚨 Kho Hàng Báo Động")
        df = get_data_frame()
        if not df.empty:
            # Lọc ra những sản phẩm sắp hết
            critical_items = df[df['stock_quantity'] <= df['alert_threshold']]
            
            if critical_items.empty:
                st.success("✅ Kho hàng tuyệt vời! Không có mã nào thiếu.")
            else:
                for idx, row in critical_items.iterrows():
                    with st.container(border=True):
                        c_img, c_info = st.columns([1, 4])
                        with c_info:
                            st.markdown(f"**{row['name']}**")
                            if row['stock_quantity'] == 0:
                                st.markdown(f":red[**HẾT HÀNG (0)**] - Mất doanh thu!")
                            else:
                                st.markdown(f":orange[**Sắp hết: {row['stock_quantity']}**] (Ngưỡng: {row['alert_threshold']})")
                        st.button("👉 Nhập ngay", key=f"btn_stock_{row['id']}")
        else:
            st.info("Chưa có dữ liệu kho.")

    # --- CỘT PHẢI: CẢNH BÁO QUẢNG CÁO (Giả lập) ---
    with col_ads:
        st.subheader("📉 Ads Kém Hiệu Quả (ROAS < 3)")
        # Giả lập danh sách Ads đang chạy
        bad_ads = [
            {"keyword": "Máy lau sàn giá rẻ", "roas": 1.5, "loss": 200000},
            {"keyword": "Nước lau sàn", "roas": 2.2, "loss": 50000},
        ]

        if not bad_ads:
            st.success("✅ Ads đang chạy ngon (ROAS > 3.0).")
        else:
            for ad in bad_ads:
                with st.container(border=True):
                    c_text, c_btn = st.columns([3, 1])
                    with c_text:
                        st.markdown(f"Từ khóa: **'{ad['keyword']}'**")
                        st.caption(f"ROAS: {ad['roas']} (Lỗ: -{ad['loss']:,} đ)")
                    with c_btn:
                        st.button("Tắt 🔥", key=f"btn_ad_{ad['keyword']}", type="primary")

# ==================================================
# TAB 2: TÍNH LÃI & THÊM MỚI (Code cũ giữ nguyên)
# ==================================================
elif menu == "💰 Tính Lãi & Niêm Yết":
    # ... (Giữ nguyên code phần này như file cũ)
    st.title("💰 CÔNG CỤ TÍNH LÃI")
    # (Copy lại phần code Tab 1 cũ vào đây)
    # ...

# ==================================================
# TAB 3: QUẢN LÝ KHO (Code cũ giữ nguyên)
# ==================================================
elif menu == "📦 Quản Lý Kho Hàng":
    # ... (Giữ nguyên code phần này như file cũ)
    st.title("📦 KHO HÀNG")
    # (Copy lại phần code Tab 2 cũ vào đây)
    # ...
