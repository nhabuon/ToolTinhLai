# ==========================================
# TOOL QUẢN TRỊ SHOPEE - BCM VERSION 2.0
# Coder: BCM-Engineer & Sếp Lâm
# Tính năng: Tính lãi + Quản lý Tồn kho (Database SQLite)
# ==========================================

import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# --- CẤU HÌNH DATABASE ---
DB_FILE = "shopee_data.db"

def init_db():
    """Khởi tạo Database và Bảng nếu chưa có"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Tạo bảng sản phẩm với cột tồn kho và cảnh báo
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

# Gọi hàm khởi tạo ngay khi chạy App
init_db()

# --- CÁC HÀM XỬ LÝ DỮ LIỆU ---
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

def get_all_products():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()
    return df

# --- GIAO DIỆN CHÍNH (STREAMLIT) ---
st.set_page_config(page_title="BCM Shopee Manager", page_icon="💎", layout="wide")

st.sidebar.title("BCM CONTROL CENTER")
menu = st.sidebar.radio("Chọn chức năng:", ["💰 Tính Lãi & Thêm Mới", "📦 Quản Lý Kho Hàng"])

# ==================================================
# TAB 1: TÍNH LÃI & THÊM SẢN PHẨM VÀO KHO
# ==================================================
if menu == "💰 Tính Lãi & Thêm Mới":
    st.title("💰 CÔNG CỤ TÍNH LÃI & NIÊM YẾT")
    st.write("Nhập thông tin để tính lãi, nếu thấy ngon thì lưu vào Kho.")

    col1, col2 = st.columns(2)
    with col1:
        ten_sp = st.text_input("Tên sản phẩm", placeholder="Ví dụ: Chổi X40 Tricut")
        gia_nhap = st.number_input("Giá nhập (Vốn)", min_value=0, step=1000, format="%d")

    with col2:
        gia_ban = st.number_input("Giá bán niêm yết", min_value=0, step=1000, format="%d")
        dong_goi = st.number_input("Chi phí đóng gói", value=2000, step=500, format="%d")

    phi_san_percent = st.slider("Phí sàn Shopee (%)", 10, 25, 16) / 100

    # Nút Tính Toán
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
            # Nút Lưu vào DB (Chỉ hiện khi đã tính lãi)
            if st.button("💾 LƯU SẢN PHẨM NÀY VÀO KHO"):
                add_product_to_db(ten_sp, gia_nhap, gia_ban)
                st.toast(f"Đã lưu '{ten_sp}' vào hệ thống!", icon="🎉")
        else:
            st.error("❌ Lỗ hoặc lãi quá mỏng! Xem lại giá.")

# ==================================================
# TAB 2: QUẢN LÝ KHO HÀNG (INVENTORY)
# ==================================================
elif menu == "📦 Quản Lý Kho Hàng":
    st.title("📦 KHO HÀNG & CẢNH BÁO TỒN KHO")
    
    # Load dữ liệu từ Database
    df = get_all_products()

    if df.empty:
        st.warning("Kho đang trống. Hãy sang tab 'Tính Lãi' để thêm sản phẩm mới!")
    else:
        # 1. BÁO CÁO CẦN NHẬP HÀNG
        st.subheader("🚨 Cảnh Báo Nhập Hàng")
        low_stock = df[df['stock_quantity'] <= df['alert_threshold']]
        
        if not low_stock.empty:
            for index, row in low_stock.iterrows():
                msg = f"SẢN PHẨM: **{row['name']}** - Chỉ còn: **{row['stock_quantity']}** (Mức báo động: {row['alert_threshold']})"
                if row['stock_quantity'] == 0:
                    st.error(f"🔴 HẾT HÀNG: {msg} -> Tắt quảng cáo ngay!")
                else:
                    st.warning(f"🟡 SẮP HẾT: {msg} -> Nhập thêm đi Sếp!")
        else:
            st.success("🟢 Tình trạng kho ổn định. Chưa có mã nào báo động.")

        st.divider()

        # 2. DANH SÁCH & CẬP NHẬT TỒN KHO
        st.subheader("📋 Danh Sách Sản Phẩm")
        
        # Hiển thị bảng đẹp hơn
        st.dataframe(df[['id', 'name', 'stock_quantity', 'selling_price']], use_container_width=True)

        st.write("### 🛠️ Cập Nhật Nhanh Tồn Kho")
        c1, c2, c3 = st.columns([3, 2, 2])
        
        with c1:
            # Chọn sản phẩm từ danh sách
            product_options = df.set_index('id')['name'].to_dict()
            selected_id = st.selectbox("Chọn sản phẩm:", options=list(product_options.keys()), format_func=lambda x: product_options[x])
        
        with c2:
            qty_change = st.number_input("Số lượng (+ Nhập, - Bán)", step=1, value=0)
            
        with c3:
            st.write("") # Spacer
            st.write("")
            if st.button("Cập nhật Kho"):
                if qty_change != 0:
                    update_stock(selected_id, qty_change)
                    st.toast("Đã cập nhật tồn kho thành công!", icon="✅")
                    st.rerun() # Load lại trang để cập nhật số mới
                else:
                    st.warning("Nhập số lượng khác 0 nhé Sếp!")

# Footer
st.sidebar.divider()
st.sidebar.caption("BCM System v2.0 - Powered by Sếp Lâm")
