# ==============================================================================
# BCM CLOUD v4.0 - FINAL WEAPON (LINE SCANNER TECH)
# Coder: BCM-Engineer (An) & Sếp Lâm
# Update: Fix lỗi file CSV có cấu trúc dòng không đồng nhất (ParserError)
# ==============================================================================

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document
import re
import io
import csv

# ==================================================
# 1. CẤU HÌNH HỆ THỐNG
# ==================================================
st.set_page_config(page_title="BCM Cloud v4.0 - MIT Corp", page_icon="🦅", layout="wide")
st.markdown("""<style>.stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 5px;} [data-testid="stMetricValue"] {font-size: 1.5rem !important;}</style>""", unsafe_allow_html=True)

# Lấy API Key
AI_STATUS = "Offline 🔴"
try:
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        AI_STATUS = "Online 🟢"
except: pass

MODEL_NAME = "gemini-3-pro-preview"
DB_FILE = "shopee_data_v3.db"
REPORT_FILE = "BAO_CAO_KINH_DOANH.xlsx"

# ==================================================
# 2. HÀM DATABASE (GIỮ NGUYÊN)
# ==================================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, cost_price INTEGER, selling_price INTEGER, stock_quantity INTEGER DEFAULT 0, alert_threshold INTEGER DEFAULT 5, daily_sales REAL DEFAULT 1.0, lead_time INTEGER DEFAULT 15, safety_stock INTEGER DEFAULT 5)''')
    c.execute('''CREATE TABLE IF NOT EXISTS financials (date TEXT PRIMARY KEY, revenue INTEGER DEFAULT 0, ad_spend INTEGER DEFAULT 0, profit INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS competitors (comp_id INTEGER PRIMARY KEY AUTOINCREMENT, my_product_name TEXT, comp_name TEXT, comp_url TEXT, comp_price INTEGER, last_check TEXT)''')
    conn.commit(); conn.close()
init_db()

def get_products_df(): conn=sqlite3.connect(DB_FILE); df=pd.read_sql_query("SELECT * FROM products", conn); conn.close(); return df
def get_products_list(): df=get_products_df(); return df['name'].tolist() if not df.empty else []
def get_my_price(n): conn=sqlite3.connect(DB_FILE); c=conn.cursor(); c.execute("SELECT selling_price FROM products WHERE name=?",(n,)); r=c.fetchone(); conn.close(); return r[0] if r else 0
def add_product(n,c,p,d,l,s): t=int(d*l+s); conn=sqlite3.connect(DB_FILE); cur=conn.cursor(); cur.execute("INSERT INTO products (name,cost_price,selling_price,daily_sales,lead_time,safety_stock,alert_threshold) VALUES (?,?,?,?,?,?,?)",(n,c,p,d,l,s,t)); conn.commit(); conn.close()
def update_stock(i,a): conn=sqlite3.connect(DB_FILE); c=conn.cursor(); c.execute("UPDATE products SET stock_quantity=stock_quantity+? WHERE id=?",(a,i)); conn.commit(); conn.close()
def add_competitor(m,c,u,p): d=datetime.now().strftime("%Y-%m-%d"); conn=sqlite3.connect(DB_FILE); cur=conn.cursor(); cur.execute("INSERT INTO competitors (my_product_name,comp_name,comp_url,comp_price,last_check) VALUES (?,?,?,?,?)",(m,c,u,p,d)); conn.commit(); conn.close()
def get_competitors_df(): conn=sqlite3.connect(DB_FILE); df=pd.read_sql_query("SELECT * FROM competitors", conn); conn.close(); return df
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

def get_file_content(uploaded_file):
    text = ""
    try:
        if uploaded_file.name.endswith(".pdf"):
            pdf_reader = PdfReader(uploaded_file); 
            for page in pdf_reader.pages: text += page.extract_text() + "\n"
        elif uploaded_file.name.endswith(".docx"):
            doc = Document(uploaded_file); 
            for para in doc.paragraphs: text += para.text + "\n"
        elif uploaded_file.name.endswith(".txt"): text = uploaded_file.read().decode("utf-8")
    except: pass
    return text

# ==================================================
# 3. TRÁI TIM XỬ LÝ FILE (CÔNG NGHỆ SCAN LINE)
# ==================================================

def convert_vn_currency(val):
    """Chuyển tiền VN: 14.267.984 -> 14267984"""
    if pd.isna(val): return 0
    s = str(val)
    s = re.sub(r'[^\d.,-]', '', s) 
    
    # Logic đoán dấu
    if s.count('.') > 1: s = s.replace('.', '') # 14.267.984
    elif '.' in s and ',' in s: s = s.replace('.', '').replace(',', '.') # 1.200,50
    elif ',' in s: s = s.replace(',', '.') # 123,45
    elif '.' in s: # 123.456 (Giả định là nghìn nếu 3 số sau chấm)
        parts = s.split('.')
        if len(parts) > 1 and len(parts[-1]) == 3: s = s.replace('.', '')
        
    try: return float(s)
    except: return 0

def scan_file_for_header(file):
    """
    Đọc file như văn bản thuần túy để tìm dòng tiêu đề.
    Tránh lỗi 'ParserError' của pandas khi số cột không đều.
    """
    encodings = ['utf-8', 'utf-16', 'latin1', 'utf-8-sig']
    content = file.getvalue()
    
    decoded_lines = []
    used_encoding = 'utf-8'
    
    # 1. Thử giải mã file
    for enc in encodings:
        try:
            decoded_lines = content.decode(enc).splitlines()
            used_encoding = enc
            break
        except: continue
        
    if not decoded_lines: return None, 0, "Không đọc được encoding"

    # 2. Quét tìm dòng tiêu đề
    # Từ khóa nhận diện header chuẩn của Shopee
    keywords = ["tổng doanh số (vnd)", "mã đơn hàng", "chi phí", "tên dịch vụ hiển thị", "ngày đặt hàng", "tổng tiền", "ngày"]
    
    header_idx = -1
    for i, line in enumerate(decoded_lines[:30]): # Chỉ quét 30 dòng đầu
        line_lower = line.lower()
        if any(k in line_lower for k in keywords):
            header_idx = i
            break
            
    if header_idx == -1: return None, 0, "Không tìm thấy từ khóa tiêu đề"

    # 3. Đọc pandas từ dòng đó
    file.seek(0)
    try:
        if file.name.endswith(('xls', 'xlsx')):
            df = pd.read_excel(file, header=header_idx)
        else:
            # Dùng đúng encoding đã tìm được
            df = pd.read_csv(file, header=header_idx, encoding=used_encoding, on_bad_lines='skip')
        return df, header_idx, "OK"
    except Exception as e:
        return None, 0, str(e)

def process_shopee_files(revenue_file, ads_file):
    total_rev = 0; total_ads = 0
    logs = []

    # --- XỬ LÝ DOANH THU ---
    if revenue_file:
        df, h_idx, status = scan_file_for_header(revenue_file)
        if df is not None:
            logs.append(f"✅ Doanh Thu: Header dòng {h_idx+1}")
            # Tìm cột tiền
            col_target = None
            # Cột chính xác trong file mẫu của Sếp là "Tổng doanh số (VND)"
            kw_rev = ["tổng doanh số (vnd)", "doanh số (vnd)", "tổng tiền", "doanh thu", "thành tiền"]
            for col in df.columns:
                if any(k in str(col).lower() for k in kw_rev):
                    col_target = col
                    break
            
            if col_target:
                logs.append(f"👉 Cột tiền: {col_target}")
                total_rev = df[col_target].apply(convert_vn_currency).sum()
            else:
                logs.append(f"⚠️ Không thấy cột tiền. Các cột có: {list(df.columns)}")
        else: logs.append(f"❌ Lỗi Doanh Thu: {status}")

    # --- XỬ LÝ ADS ---
    if ads_file:
        df, h_idx, status = scan_file_for_header(ads_file)
        if df is not None:
            logs.append(f"✅ Ads: Header dòng {h_idx+1}")
            # Tìm cột chi phí
            col_target = None
            # Cột chính xác trong file mẫu là "Chi phí"
            kw_ads = ["chi phí", "cost", "tiền chạy"]
            for col in df.columns:
                if any(k in str(col).lower() for k in kw_ads):
                    col_target = col
                    break
            
            if col_target:
                logs.append(f"👉 Cột chi phí: {col_target}")
                total_ads = df[col_target].apply(convert_vn_currency).sum()
            else:
                logs.append(f"⚠️ Không thấy cột phí. Các cột có: {list(df.columns)}")
        else: logs.append(f"❌ Lỗi Ads: {status}")

    return total_rev, total_ads, logs

# ==================================================
# 4. GIAO DIỆN CHÍNH
# ==================================================
with st.sidebar:
    st.title("🦅 BCM Cloud v4.0")
    st.caption(f"Engine: {MODEL_NAME} | Status: {AI_STATUS}")
    st.markdown("---")
    menu = st.radio("Menu:", ["🤖 Phòng Họp Chiến Lược", "📊 Báo Cáo & Excel", "⚔️ Rada Đối Thủ", "💰 Tính Lãi & Thêm Mới", "📦 Kho Hàng"])
    
    if menu == "🤖 Phòng Họp Chiến Lược":
        st.markdown("---")
        st.subheader("📂 RAG (Nạp tài liệu)")
        uploaded_files = st.file_uploader("Upload PDF/Word:", accept_multiple_files=True, type=['pdf', 'docx', 'txt'])
        knowledge_context = ""
        if uploaded_files:
            with st.status("Đang học...", expanded=True) as status:
                for file in uploaded_files:
                    c = get_file_content(file)
                    if c: knowledge_context += f"\n--- DOC: {file.name} ---\n{c}\n"
                status.update(label="Đã học xong!", state="complete", expanded=False)

# ==================================================
# 5. LOGIC MODULES
# ==================================================

if menu == "📊 Báo Cáo & Excel":
    st.title("📊 BÁO CÁO KINH DOANH (SCANNER MODE)")
    st.info("💡 Hỗ trợ mọi loại file lỗi cấu trúc, tự động tìm dòng tiêu đề.")
    d = st.date_input("Chọn tuần:", datetime.now())
    
    with st.expander("📂 UPLOAD FILE SHOPEE", expanded=True):
        f1 = st.file_uploader("File Doanh Thu (Shop Stats)")
        f2 = st.file_uploader("File Quảng Cáo (Ads)")
        
        if f1 or f2:
            rev, ads, debug_info = process_shopee_files(f1, f2)
            with st.expander("🔍 Kiểm tra Nhật Ký Xử Lý (Log)"):
                for l in debug_info: st.write(l)
                if rev == 0 and ads == 0: st.error("Vẫn chưa đọc được số liệu. Hãy chụp màn hình bảng log này gửi An!")

    st.divider()
    c1, c2, c3 = st.columns(3)
    nr = c1.number_input("Doanh thu", float(rev), step=1e5, format="%.0f")
    na = c2.number_input("Chi phí Ads", float(ads), step=5e4, format="%.0f")
    np = c3.number_input("Lợi nhuận Ròng (30%)", float(nr*0.3-na), step=5e4, format="%.0f")
    
    if st.button("💾 LƯU & XUẤT EXCEL", type="primary"):
        fp = save_report_to_excel(d, nr, na, np)
        st.success(f"✅ Đã xuất báo cáo: {fp}")

elif menu == "🤖 Phòng Họp Chiến Lược":
    st.header("🤖 PHÒNG HỌP CHIẾN LƯỢC")
    df_comp = get_competitors_df()
    comp_context = f"\n--- THỊ TRƯỜNG ---\n{df_comp.to_string()}\n" if not df_comp.empty else ""
    role = st.radio("Nhân sự:", ["An (Kỹ sư)", "Sư (Cố vấn)"], horizontal=True)
    st.divider()
    
    if "messages" not in st.session_state: st.session_state.messages = []
    for msg in st.session_state.messages: st.chat_message(msg["role"]).markdown(msg["content"])
    
    if p := st.chat_input("Ra lệnh..."):
        st.session_state.messages.append({"role": "user", "content": p})
        st.chat_message("user").markdown(p)
        base = f"{knowledge_context}\n{comp_context}" if 'knowledge_context' in locals() else comp_context
        sys = f"Bạn là {role}. Dựa vào dữ liệu: {base}. Trả lời câu hỏi: {p}"
        
        with st.chat_message("assistant"):
            if AI_STATUS == "Online 🟢":
                try:
                    res = genai.GenerativeModel(MODEL_NAME).generate_content(sys).text
                    st.markdown(res)
                    st.session_state.messages.append({"role": "assistant", "content": res})
                except Exception as e: st.error(str(e))
            else: st.error("AI Offline")

elif menu == "⚔️ Rada Đối Thủ":
    st.title("⚔️ RADA ĐỐI THỦ")
    with st.expander("Thêm Đối Thủ"):
        my_l = get_products_list()
        if my_l:
            c1,c2 = st.columns(2)
            p_me = c1.selectbox("SP Mình", my_l)
            p_shop = c1.text_input("Tên Shop")
            p_link = c2.text_input("Link"); p_pr = c2.number_input("Giá", step=1000)
            if st.button("Lưu"): add_competitor(p_me, p_shop, p_link, p_pr); st.rerun()
        else: st.warning("Kho trống!")
    df = get_competitors_df()
    if not df.empty: st.dataframe(df)

elif menu == "💰 Tính Lãi & Thêm Mới":
    st.title("💰 TÍNH LÃI"); c1,c2,c3=st.columns(3)
    n=c1.text_input("Tên"); v=c1.number_input("Vốn",1000)
    b=c2.number_input("Bán",1000); h=c2.number_input("Gói",2000)
    d=c3.number_input("Ngày bán",1.0); l=c3.number_input("Ship",15); s=c3.number_input("Safe",5)
    f=st.slider("Phí sàn %",0,30,16)
    if st.button("Tính & Lưu"):
        lai=b*(1-f/100)-v-h; add_product(n,v,b,d,l,s) if lai>0 else None
        st.metric("Lãi", f"{lai:,.0f}")

elif menu == "📦 Kho Hàng":
    st.title("📦 KHO HÀNG"); df=get_products_df()
    if not df.empty:
        st.dataframe(df)
        with st.form("k"):
            i=st.selectbox("SP",df['id'],format_func=lambda x:df[df['id']==x]['name'].values[0])
            q=st.number_input("+/-",step=1)
            if st.form_submit_button("Lưu"): update_stock(i,q); st.rerun()
