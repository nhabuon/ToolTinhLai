# ==========================================
# TOOL TÍNH LÃI SHOPEE - PHIÊN BẢN WEB
# Coder: BCM-Engineer (Sếp Lâm)
# ==========================================

import streamlit as st # Thư viện làm web
import os
from datetime import datetime
from docx import Document

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Shopee Profit Tool", page_icon="💰")

st.title("💰 CÔNG CỤ TÍNH LÃI SHOPEE")
st.write("Sếp Lâm nhập số liệu vào bên dưới nhé:")

# --- KHU VỰC NHẬP LIỆU (INPUT) ---
col1, col2 = st.columns(2) # Chia làm 2 cột cho đẹp

with col1:
    ten_sp = st.text_input("Tên sản phẩm", "Ví dụ: Robot T30")
    gia_nhap = st.number_input("Giá nhập (Vốn)", min_value=0, step=1000)

with col2:
    gia_ban = st.number_input("Giá bán niêm yết", min_value=0, step=1000)
    dong_goi = st.number_input("Chi phí đóng gói", value=2000, step=500)

# Cấu hình phí sàn
phi_san_percent = st.slider("Tổng % Phí Sàn (Mặc định 16%)", 10, 25, 16) / 100

# --- NÚT BẤM TÍNH TOÁN ---
if st.button("🚀 TÍNH LÃI NGAY", type="primary"):
    # 1. Tính toán logic
    tien_phi_san = gia_ban * phi_san_percent
    doanh_thu_thuc = gia_ban - tien_phi_san
    lai_rong = doanh_thu_thuc - gia_nhap - dong_goi
    
    if gia_ban > 0:
        ty_suat = (lai_rong / gia_ban) * 100
    else:
        ty_suat = 0

    # 2. Hiển thị kết quả ra màn hình Web
    st.divider()
    st.subheader(f"Kết quả cho: {ten_sp}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Sàn thu phí", f"{tien_phi_san:,.0f} đ")
    c2.metric("Vốn + Hộp", f"{gia_nhap + dong_goi:,.0f} đ")
    c3.metric("LÃI RÒNG", f"{lai_rong:,.0f} đ", delta=f"{ty_suat:.1f}%")

    # Thông báo trạng thái
    if lai_rong > 0:
        st.success("✅ Kèo này thơm! Triển khai thôi Sếp!")
    else:
        st.error("❌ Kèo này lỗ hoặc hòa vốn! Cân nhắc tăng giá.")

    # 3. Lưu vào Word (Code cũ)
    file_name = "Nhat_Ky_Ban_Hang.docx"
    try:
        if os.path.exists(file_name):
            doc = Document(file_name)
        else:
            doc = Document()
            doc.add_heading('NHẬT KÝ TÍNH LÃI', 0)
        
        p = doc.add_paragraph()
        p.add_run(f"{datetime.now().strftime('%H:%M')} - {ten_sp}: ").bold = True
        p.add_run(f"Lãi {lai_rong:,.0f} đ (Giá bán: {gia_ban:,.0f})")
        doc.save(file_name)
        st.toast(f"Đã lưu kết quả vào file {file_name}")
    except:
        st.warning("⚠️ Đang mở file Word nên không lưu được. Sếp tắt Word đi nhé!")