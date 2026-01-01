# ==========================================
# TOOL QUẢN TRỊ SHOPEE - BCM VERSION 3.5 (FINAL)
# Coder: BCM-Engineer (An) & Sếp Lâm
# Engine: Gemini 3 Pro Preview
# Tính năng: Dual Persona (An & Sư), Radar, Báo cáo Excel, Kho Offline
# ==========================================

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from google import genai
import time
import os

# ==================================================
# ⚙️ KHU VỰC CẤU HÌNH CỨNG
# ==================================================
# 1. API Key: Sếp dán Key vào giữa 2 dấu ngoặc kép bên dưới để dùng luôn
MY_API_KEY = "" 

# 2. Cấu hình File
DB_FILE = "shopee_data_v3.db"            # Database nội bộ
REPORT_FILE = "BAO_CAO_KINH_DOANH.xlsx"  # File xuất báo cáo

# 3. Model AI (Mới nhất 2026)
AI_MODEL_ID = 'gemini-3-pro-preview' 

# ==================================================

# --- 1. KHỞI TẠO DATABASE (SQLITE) ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Bảng Sản Phẩm
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
    # Bảng Tài Chính
    c.execute('''CREATE TABLE IF NOT EXISTS financials (
                    date TEXT PRIMARY KEY,
                    revenue INTEGER DEFAULT 0,
                    ad_spend INTEGER DEFAULT 0,
                    profit INTEGER DEFAULT 0
                )''')
    # Bảng Đối Thủ (Radar)
    c.execute('''CREATE TABLE IF NOT EXISTS competitors (
                    comp_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    my_product_name TEXT,
                    comp_name TEXT,
                    comp_url TEXT,
                    comp_price INTEGER,
                    last_check TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

# --- 2. CÁC HÀM XỬ LÝ DỮ LIỆU ---

def get_products_df():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()
    return df

def get_products_list():
    df = get_products_df()
    return df['name'].tolist() if not df.empty else []

def get_my_price(product_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT selling_price FROM products WHERE name = ?", (product_name,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0

def add_product(name, cost, price, daily, lead, safe):
    threshold = int(daily * lead + safe)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""INSERT INTO products (name, cost_price, selling_price, daily_sales, lead_time, safety_stock, alert_threshold) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)""", (name, cost, price, daily, lead, safe, threshold))
    conn.commit()
    conn.close()

def update_stock(pid, amount):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (amount, pid))
    conn.commit()
    conn.close()

def add_competitor(my_prod, comp_name, url, price):
    date_now = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO competitors (my_product_name, comp_name, comp_url, comp_price, last_check) VALUES (?, ?, ?, ?, ?)",
              (my_prod, comp_name, url, price, date_now))
    conn.commit()
    conn.close()

def get_competitors_df():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM competitors", conn)
    conn.close()
    return df

def update_comp_price(comp_id, new_price):
    date_now = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE competitors SET comp_price = ?, last_check = ? WHERE comp_id = ?", (new_price, date_now, comp_id))
    conn.commit()
    conn.close()

def save_report_to_excel(date_obj, rev, ads, prof):
    # Lưu vào DB
    start_date = (date_obj - timedelta(days=date_obj.weekday())).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO financials (date, revenue, ad_spend, profit) VALUES (?, ?, ?, ?)", (start_date, rev, ads, prof))
    conn.commit()
    conn.close()
    
    # Lưu ra Excel
    data = {
        'Ngày Báo Cáo': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        'Tuần Kinh Doanh': [start_date],
        'Doanh Thu': [rev],
        'Chi Phí Ads': [ads],
        'Lợi Nhuận': [prof]
    }
    df_new = pd.DataFrame(data)
    
    if os.path.exists(REPORT_FILE):
        with pd.ExcelWriter(REPORT_FILE, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
            try:
                writer.book = pd.read_excel(REPORT_FILE)
                start_row = writer.sheets['Sheet1'].max_row
                df_new.to_excel(writer, index=False, header=False, startrow=start_row)
            except:
                 df_new.to_excel(REPORT_FILE, index=False)
    else:
        df_new.to_excel(REPORT_FILE, index=False)
    return REPORT_FILE

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

# --- 3. GIAO DIỆN CHÍNH (STREAMLIT UI) ---
st.set_page_config(page_title="BCM v3.5 Dual Core", page_icon="🦅", layout="wide")
st.markdown("""<style>.stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 5px;} [data-testid="stMetricValue"] {font-size: 1.5rem !important;}</style>""", unsafe_allow_html=True)

# SIDEBAR
st.sidebar.title("BCM v3.5 (Gemini 3)")
st.sidebar.caption(f"Engine: {AI_MODEL_ID}")

client = None
if MY_API_KEY: api_key = MY_API_KEY
else: api_key = st.sidebar.text_input("Nhập Key AI:", type="password")

if api_key:
    try: client = genai.Client(api_key=api_key); st.sidebar.success("AI Online 🟢")
    except: pass

menu = st.sidebar.radio("Menu:", ["🤖 Phòng Họp Chiến Lược (Dual)", "📊 Báo Cáo & Xuất Excel", "⚔️ Rada Đối Thủ", "💰 Tính Lãi & Thêm Mới", "📦 Kho Hàng"])

# ================= TAB 1: PHÒNG HỌP CHIẾN LƯỢC (ĐA NHÂN CÁCH) =================
if menu == "🤖 Phòng Họp Chiến Lược (Dual)":
    st.title("🤖 PHÒNG HỌP CHIẾN LƯỢC")
    st.caption("Tham vấn ý kiến của các nhân sự AI cốt cán.")

    if not client:
        st.error("⚠️ Vui lòng nhập API Key để triệu tập nhân viên.")
    else:
        # CHỌN NHÂN SỰ
        col_nv, col_chat = st.columns([1, 3])
        
        with col_nv:
            st.subheader("Chọn Người Tư Vấn:")
            nhan_vien = st.radio(
                "Nhân sự:",
                ["An (Kỹ sư BCM)", "Sư (Cố vấn Khắt khe)"],
                captions=["Hỗ trợ, kỹ thuật, giải pháp.", "Phản biện, soi mói, đa nghi."]
            )
            
            if "An" in nhan_vien:
                st.info("🔵 **An:**\n- Nhiệt tình, Support.\n- Giỏi tính toán, Code.\n- Luôn tìm giải pháp.")
            else:
                st.error("🔴 **Sư:**\n- Khó tính, hay nghi ngờ.\n- Đóng vai Đối thủ/Khách khó tính.\n- Chuyên tìm lỗi & rủi ro.")

        with col_chat:
            # Lấy context dữ liệu
            df_comp = get_competitors_df()
            context_info = ""
            if not df_comp.empty:
                context_info = f"Dữ liệu thị trường hiện tại (Đối thủ):\n{df_comp.to_string()}\n"
            
            st.subheader(f"💬 Đang trao đổi với: {nhan_vien.split(' ')[0]}")
            user_input = st.text_area("Sếp muốn hỏi gì?", height=100, placeholder="VD: Chiến lược giá này ổn không? Content này đã hay chưa?")
            
            if st.button("Hỏi ngay 🚀"):
                if not user_input:
                    st.warning("Sếp chưa nhập câu hỏi...")
                else:
                    with st.spinner(f"{nhan_vien.split(' ')[0]} đang suy nghĩ..."):
                        # --- THIẾT LẬP PROMPT ---
                        if "An" in nhan_vien:
                            system_prompt = f"""
                            Bạn là An, Kỹ sư BCM nhiệt huyết, trợ lý của Sếp Lâm.
                            Tính cách: Nhanh nhẹn, lạc quan, tập trung vào giải pháp (Solution-oriented).
                            Nhiệm vụ: Dùng dữ liệu sau để trả lời Sếp một cách xây dựng:
                            {context_info}
                            Câu hỏi: {user_input}
                            """
                        else:
                            system_prompt = f"""
                            Bạn là 'Sư' (Advisor) - Cố vấn chiến lược cực kỳ khó tính, đa nghi và cay nghiệt.
                            Tuyệt đối KHÔNG khen xã giao.
                            Nhiệm vụ:
                            1. Đóng vai Khách hàng khó tính bắt bẻ sản phẩm.
                            2. Hoặc đóng vai Đối thủ cạnh tranh tìm cách dìm hàng.
                            3. Chỉ ra LỖ HỔNG (Loophole), RỦI RO (Risk) mà Sếp Lâm đang ảo tưởng.
                            Dữ liệu thị trường:
                            {context_info}
                            Câu hỏi (hãy soi mói câu này): {user_input}
                            """
                        
                        try:
                            response = client.models.generate_content(
                                model=AI_MODEL_ID,
                                contents=system_prompt
                            )
                            if "An" in nhan_vien:
                                st.success(response.text)
                            else:
                                st.warning(response.text) 
                        except Exception as e:
                            st.error(f"Lỗi AI: {e}")

# ================= TAB 2: BÁO CÁO =================
elif menu == "📊 Báo Cáo & Xuất Excel":
    st.title("📊 BÁO CÁO KINH DOANH")
    st.caption(f"File lưu tại: **{REPORT_FILE}**")
    d = st.date_input("Chọn tuần:", datetime.now())
    with st.expander("Upload File"):
        f1=st.file_uploader("Doanh Thu"); f2=st.file_uploader("Ads")
        arev, aads = process_shopee_files(f1, f2)
    st.divider()
    c1, c2, c3 = st.columns(3)
    nr = c1.number_input("Doanh thu", float(arev) if arev else 0.0, step=1e5, format="%.0f")
    na = c2.number_input("Chi phí Ads", float(aads) if aads else 0.0, step=5e4, format="%.0f")
    np = c3.number_input("Lợi nhuận Ròng", float(nr*0.3-na), step=5e4, format="%.0f")
    if st.button("💾 LƯU & XUẤT EXCEL", type="primary"):
        fp = save_report_to_excel(d, nr, na, np)
        st.success(f"✅ Đã xuất báo cáo: {fp}")

# ================= TAB 3: RADA =================
elif menu == "⚔️ Rada Đối Thủ":
    st.title("⚔️ RADA ĐỐI THỦ")
    with st.expander("➕ Thêm Đối Thủ"):
        my_prods = get_products_list()
        if not my_prods: st.warning("Kho trống!")
        else:
            c1, c2 = st.columns(2)
            with c1: p_me = st.selectbox("SP Mình", my_prods); p_shop = st.text_input("Tên Shop")
            with c2: p_link = st.text_input("Link"); p_price = st.number_input("Giá", step=1000)
            if st.button("Lưu"): add_competitor(p_me, p_shop, p_link, p_price); st.rerun()
    
    df_comp = get_competitors_df()
    if not df_comp.empty:
        prod = st.selectbox("🔍 Soi SP:", df_comp['my_product_name'].unique())
        df_view = df_comp[df_comp['my_product_name'] == prod]
        if not df_view.empty:
            prices = df_view['comp_price'].tolist(); my_p = get_my_price(prod); avg_p = sum(prices)/len(prices)
            st.divider(); m1, m2, m3 = st.columns(3)
            m1.metric("Min", f"{min(prices):,.0f}"); m2.metric("Avg", f"{avg_p:,.0f}"); m3.metric("Max", f"{max(prices):,.0f}")
            delta = my_p - avg_p
            if delta>0: st.metric("GIÁ SẾP", f"{my_p:,.0f}", f"Cao hơn {delta/avg_p*100:.1f}% 🔴", delta_color="inverse")
            else: st.metric("GIÁ SẾP", f"{my_p:,.0f}", f"Thấp hơn {abs(delta/avg_p*100):.1f}% 🟢", delta_color="normal")
            st.write("---")
            for idx, row in df_view.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    c1.write(f"**{row['comp_name']}**"); c2.metric("Giá", f"{row['comp_price']:,.0f}")
                    np = c3.number_input("Sửa", value=row['comp_price'], key=row['comp_id'], label_visibility="collapsed")
                    if c3.button("Lưu", key=f"b_{row['comp_id']}"): update_comp_price(row['comp_id'], np); st.rerun()

# ================= TAB 4: TÍNH LÃI =================
elif menu == "💰 Tính Lãi & Thêm Mới":
    st.title("💰 CÔNG CỤ TÍNH LÃI")
    c1, c2, c3 = st.columns(3)
    with c1: ten=st.text_input("Tên SP"); von=st.number_input("Giá Vốn", step=1000)
    with c2: ban=st.number_input("Giá Bán", step=1000); hop=st.number_input("Phí gói", 2000)
    with c3: daily=st.number_input("Bán/ngày", 1.0); lead=st.number_input("Ngày ship", 15); safe=st.number_input("Safety", 5)
    san = st.slider("Phí sàn %", 0, 25, 16)
    if st.button("🚀 TÍNH & LƯU"):
        lai = ban*(1-san/100) - von - hop
        rop = int(daily*lead + safe)
        st.metric("LÃI RÒNG", f"{lai:,.0f} đ", f"Nhập khi còn: {rop} cái")
        if lai>0: add_product(ten, von, ban, daily, lead, safe); st.success("Đã lưu!")

# ================= TAB 5: KHO HÀNG =================
elif menu == "📦 Kho Hàng":
    st.title("📦 KHO HÀNG")
    df = get_products_df()
    if not df.empty:
        st.dataframe(df)
        with st.form("kho"):
            pid = st.selectbox("Chọn SP", df['id'], format_func=lambda x: df[df['id']==x]['name'].values[0])
            qty = st.number_input("Nhập/Xuất", step=1)
            if st.form_submit_button("Cập nhật"): update_stock(pid, qty); st.rerun()
