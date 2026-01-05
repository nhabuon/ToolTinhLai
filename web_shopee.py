# ==============================================================================
# BCM CLOUD v3.6 - FIX DATA PROCESSING (FINAL)
# Coder: BCM-Engineer (An) & Sếp Lâm
# Update: Fix lỗi đọc file Doanh thu/Ads Shopee = 0
# ==============================================================================

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document

# ==================================================
# 1. CẤU HÌNH HỆ THỐNG & API
# ==================================================
st.set_page_config(page_title="BCM Cloud v3.6 - MIT Corp", page_icon="🦅", layout="wide")
st.markdown("""<style>.stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 5px;} [data-testid="stMetricValue"] {font-size: 1.5rem !important;}</style>""", unsafe_allow_html=True)

# Lấy API Key
AI_STATUS = "Offline 🔴"
try:
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        AI_STATUS = "Online 🟢"
    else:
        st.error("⚠️ Chưa cấu hình GOOGLE_API_KEY trong Secrets!")
except Exception as e:
    st.error(f"Lỗi kết nối API: {e}")

# Model Config
MODEL_CONFIG = {"temperature": 0.7, "top_p": 0.95, "top_k": 64, "max_output_tokens": 8192}
MODEL_NAME = "gemini-3-pro-preview" 

# File dữ liệu
DB_FILE = "shopee_data_v3.db"
REPORT_FILE = "BAO_CAO_KINH_DOANH.xlsx"

# ==================================================
# 2. CÁC HÀM HỖ TRỢ (DATABASE & RAG)
# ==================================================

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, cost_price INTEGER, selling_price INTEGER, stock_quantity INTEGER DEFAULT 0, alert_threshold INTEGER DEFAULT 5, daily_sales REAL DEFAULT 1.0, lead_time INTEGER DEFAULT 15, safety_stock INTEGER DEFAULT 5)''')
    c.execute('''CREATE TABLE IF NOT EXISTS financials (date TEXT PRIMARY KEY, revenue INTEGER DEFAULT 0, ad_spend INTEGER DEFAULT 0, profit INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS competitors (comp_id INTEGER PRIMARY KEY AUTOINCREMENT, my_product_name TEXT, comp_name TEXT, comp_url TEXT, comp_price INTEGER, last_check TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_products_df():
    conn = sqlite3.connect(DB_FILE); df = pd.read_sql_query("SELECT * FROM products", conn); conn.close(); return df
def get_products_list():
    df = get_products_df(); return df['name'].tolist() if not df.empty else []
def get_my_price(product_name):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("SELECT selling_price FROM products WHERE name = ?", (product_name,)); res = c.fetchone(); conn.close(); return res[0] if res else 0
def add_product(name, cost, price, daily, lead, safe):
    threshold = int(daily * lead + safe)
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("INSERT INTO products (name, cost_price, selling_price, daily_sales, lead_time, safety_stock, alert_threshold) VALUES (?, ?, ?, ?, ?, ?, ?)", (name, cost, price, daily, lead, safe, threshold)); conn.commit(); conn.close()
def update_stock(pid, amount):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (amount, pid)); conn.commit(); conn.close()
def add_competitor(my_prod, comp_name, url, price):
    date_now = datetime.now().strftime("%Y-%m-%d"); conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("INSERT INTO competitors (my_product_name, comp_name, comp_url, comp_price, last_check) VALUES (?, ?, ?, ?, ?)", (my_prod, comp_name, url, price, date_now)); conn.commit(); conn.close()
def get_competitors_df():
    conn = sqlite3.connect(DB_FILE); df = pd.read_sql_query("SELECT * FROM competitors", conn); conn.close(); return df
def update_comp_price(comp_id, new_price):
    date_now = datetime.now().strftime("%Y-%m-%d"); conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("UPDATE competitors SET comp_price = ?, last_check = ? WHERE comp_id = ?", (new_price, date_now, comp_id)); conn.commit(); conn.close()
def save_report_to_excel(date_obj, rev, ads, prof):
    start_date = (date_obj - timedelta(days=date_obj.weekday())).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("REPLACE INTO financials (date, revenue, ad_spend, profit) VALUES (?, ?, ?, ?)", (start_date, rev, ads, prof)); conn.commit(); conn.close()
    data = {'Ngày Báo Cáo': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")], 'Tuần Kinh Doanh': [start_date], 'Doanh Thu': [rev], 'Chi Phí Ads': [ads], 'Lợi Nhuận': [prof]}
    df_new = pd.DataFrame(data)
    if os.path.exists(REPORT_FILE):
        with pd.ExcelWriter(REPORT_FILE, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
            try: writer.book = pd.read_excel(REPORT_FILE); start_row = writer.sheets['Sheet1'].max_row; df_new.to_excel(writer, index=False, header=False, startrow=start_row)
            except: df_new.to_excel(REPORT_FILE, index=False)
    else: df_new.to_excel(REPORT_FILE, index=False)
    return REPORT_FILE

# --- HÀM XỬ LÝ FILE (ĐÃ NÂNG CẤP THÔNG MINH) ---
def process_shopee_files(revenue_file, ads_file):
    total_revenue = 0
    total_ads = 0
    
    def clean_and_sum(df, keywords):
        # 1. Tìm cột chứa từ khóa
        found_col = None
        for col in df.columns:
            c_lower = str(col).lower()
            for kw in keywords:
                if kw in c_lower:
                    found_col = col
                    break
            if found_col: break
            
        if not found_col: return 0
        
        # 2. Xử lý dữ liệu (Số hoặc Chữ)
        if pd.api.types.is_numeric_dtype(df[found_col]):
            return df[found_col].fillna(0).sum()
        else:
            # Xóa '₫', '.', ',' và chữ cái -> Chỉ giữ lại số
            # Ví dụ: "1.500.000 ₫" -> "1500000"
            s = df[found_col].astype(str).str.replace(r'[^\d]', '', regex=True)
            return pd.to_numeric(s, errors='coerce').fillna(0).sum()

    # Xử lý File Doanh Thu
    if revenue_file:
        try:
            if revenue_file.name.endswith(('xls','xlsx')): df = pd.read_excel(revenue_file)
            else: df = pd.read_csv(revenue_file)
            # Từ khóa mở rộng: doanh thu, tổng tiền, thành tiền
            total_revenue = clean_and_sum(df, ["doanh thu", "tổng tiền", "thành tiền", "total amount", "grand total"])
        except: pass

    # Xử lý File Ads
    if ads_file:
        try:
            if ads_file.name.endswith(('xls','xlsx')): df = pd.read_excel(ads_file)
            else: df = pd.read_csv(ads_file)
            # Từ khóa: chi phí, cost
            total_ads = clean_and_sum(df, ["chi phí", "cost", "expense"])
        except: pass

    return total_revenue, total_ads

# --- RAG UTILS ---
def get_file_content(uploaded_file):
    text = ""
    try:
        if uploaded_file.name.endswith(".pdf"):
            pdf_reader = PdfReader(uploaded_file)
            for page in pdf_reader.pages: text += page.extract_text() + "\n"
        elif uploaded_file.name.endswith(".docx"):
            doc = Document(uploaded_file)
            for para in doc.paragraphs: text += para.text + "\n"
        elif uploaded_file.name.endswith(".txt"):
            text = uploaded_file.read().decode("utf-8")
    except: pass
    return text

# ==================================================
# 3. GIAO DIỆN CHÍNH
# ==================================================

with st.sidebar:
    st.title("🦅 BCM Cloud v3.6")
    st.caption(f"Engine: {MODEL_NAME} | Status: {AI_STATUS}")
    st.markdown("---")
    menu = st.radio("Chọn chức năng:", ["🤖 Phòng Họp Chiến Lược", "📊 Báo Cáo & Excel", "⚔️ Rada Đối Thủ", "💰 Tính Lãi & Thêm Mới", "📦 Kho Hàng"])
    
    if menu == "🤖 Phòng Họp Chiến Lược":
        st.markdown("---")
        st.subheader("📂 Kho Tri Thức (RAG)")
        uploaded_files = st.file_uploader("Nạp tài liệu (PDF, Word):", accept_multiple_files=True, type=['pdf', 'docx', 'txt'])
        knowledge_context = ""
        if uploaded_files:
            with st.status("Đang học dữ liệu...", expanded=True) as status:
                for file in uploaded_files:
                    content = get_file_content(file)
                    if content: knowledge_context += f"\n--- TÀI LIỆU: {file.name} ---\n{content}\n"
                status.update(label="Đã nạp xong kiến thức!", state="complete", expanded=False)

# ==================================================
# 4. LOGIC MODULES
# ==================================================

if menu == "🤖 Phòng Họp Chiến Lược":
    st.header("🤖 PHÒNG HỌP CHIẾN LƯỢC (DUAL CORE)")
    df_comp = get_competitors_df()
    comp_context = f"\n--- DỮ LIỆU THỊ TRƯỜNG (Từ Radar) ---\n{df_comp.to_string()}\n" if not df_comp.empty else ""
    
    role = st.radio("Chọn nhân sự:", ["🔴 An (RCM Engineer)", "🟡 Sư (Advisor)"], horizontal=True)
    st.divider()

    if "messages" not in st.session_state: st.session_state.messages = []
    for message in st.session_state.messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])

    if prompt := st.chat_input("Ra lệnh cho hệ thống..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        base_context = f"{knowledge_context}\n{comp_context}" if 'knowledge_context' in locals() else comp_context
        
        if "An" in role:
            sys_inst = f"Bạn là An - Kỹ sư BCM. Phong cách: Kỹ thuật, Cụ thể. Dữ liệu: {base_context}"
        else:
            sys_inst = f"Bạn là Sư (Advisor). Phong cách: Chiến lược, Soi mói rủi ro. Dữ liệu: {base_context}"
            
        full_prompt = f"{sys_inst}\n\nCâu hỏi: {prompt}"

        with st.chat_message("assistant"):
            if AI_STATUS == "Online 🟢":
                try:
                    model = genai.GenerativeModel(MODEL_NAME)
                    response = model.generate_content(full_prompt, stream=True)
                    full_res = ""
                    ph = st.empty()
                    for chunk in response:
                        if chunk.text: full_res += chunk.text; ph.markdown(full_res + "▌")
                    ph.markdown(full_res)
                    st.session_state.messages.append({"role": "assistant", "content": full_res})
                except Exception as e: st.error(f"Lỗi AI: {e}")
            else: st.error("⚠️ AI Offline. Check Secrets!")

elif menu == "📊 Báo Cáo & Excel":
    st.title("📊 BÁO CÁO KINH DOANH")
    st.info("💡 Mẹo: Hỗ trợ cả file 'Phân Tích Bán Hàng' và 'Danh Sách Đơn Hàng'.")
    d = st.date_input("Chọn tuần:", datetime.now())
    with st.expander("Upload File Shopee", expanded=True):
        f1=st.file_uploader("File Doanh Thu (Excel/CSV)"); f2=st.file_uploader("File Ads (Excel/CSV)")
        arev, aads = process_shopee_files(f1, f2)
    
    st.divider()
    c1, c2, c3 = st.columns(3)
    nr = c1.number_input("Doanh thu", float(arev), step=1e5, format="%.0f")
    na = c2.number_input("Chi phí Ads", float(aads), step=5e4, format="%.0f")
    np = c3.number_input("Lợi nhuận Ròng (30%)", float(nr*0.3-na), step=5e4, format="%.0f")
    
    if st.button("💾 LƯU & XUẤT EXCEL", type="primary"):
        fp = save_report_to_excel(d, nr, na, np)
        st.success(f"✅ Đã xuất báo cáo: {fp}")

elif menu == "⚔️ Rada Đối Thủ":
    st.title("⚔️ RADA ĐỐI THỦ")
    with st.expander("➕ Thêm Đối Thủ"):
        my_prods = get_products_list()
        if my_prods:
            c1, c2 = st.columns(2)
            with c1: p_me = st.selectbox("SP Mình", my_prods); p_shop = st.text_input("Tên Shop")
            with c2: p_link = st.text_input("Link"); p_price = st.number_input("Giá Họ", step=1000)
            if st.button("Lưu"): add_competitor(p_me, p_shop, p_link, p_price); st.rerun()
        else: st.warning("Kho trống!")
    
    df_comp = get_competitors_df()
    if not df_comp.empty:
        prod = st.selectbox("🔍 Soi Sản Phẩm:", df_comp['my_product_name'].unique())
        df_view = df_comp[df_comp['my_product_name'] == prod]
        if not df_view.empty:
            prices = df_view['comp_price'].tolist(); my_p = get_my_price(prod); avg_p = sum(prices)/len(prices)
            st.divider(); m1, m2, m3 = st.columns(3)
            m1.metric("Min", f"{min(prices):,.0f}"); m2.metric("Avg", f"{avg_p:,.0f}"); m3.metric("Max", f"{max(prices):,.0f}")
            st.dataframe(df_view)

elif menu == "💰 Tính Lãi & Thêm Mới":
    st.title("💰 TÍNH LÃI")
    c1, c2, c3 = st.columns(3)
    with c1: ten=st.text_input("Tên SP"); von=st.number_input("Giá Vốn", step=1000)
    with c2: ban=st.number_input("Giá Bán", step=1000); hop=st.number_input("Phí gói", 2000)
    with c3: daily=st.number_input("Bán/ngày", 1.0); lead=st.number_input("Ngày ship", 15); safe=st.number_input("Safety", 5)
    san = st.slider("Phí sàn %", 0, 30, 16)
    if st.button("🚀 TÍNH & LƯU"):
        lai = ban*(1-san/100) - von - hop
        if lai>0: add_product(ten, von, ban, daily, lead, safe); st.success("Đã lưu!")
        st.metric("LÃI RÒNG", f"{lai:,.0f} đ")

elif menu == "📦 Kho Hàng":
    st.title("📦 KHO HÀNG")
    df = get_products_df()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        with st.form("kho"):
            pid = st.selectbox("Chọn SP", df['id'], format_func=lambda x: df[df['id']==x]['name'].values[0])
            qty = st.number_input("Nhập/Xuất", step=1)
            if st.form_submit_button("Cập nhật"): update_stock(pid, qty); st.rerun()
