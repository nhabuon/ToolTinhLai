# ==============================================================================
# BCM CLOUD v4.1 - FORCE DECODE & ENGINE PYTHON (FINAL PATCH)
# Coder: BCM-Engineer (An) & Sếp Lâm
# Update: Dùng engine='python' để bỏ qua dòng lỗi, sửa lỗi đọc file 0đ
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

# ==================================================
# 1. CẤU HÌNH HỆ THỐNG
# ==================================================
st.set_page_config(page_title="BCM Cloud v4.1 - MIT Corp", page_icon="🦅", layout="wide")
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
# 3. TRÁI TIM XỬ LÝ FILE (CÔNG NGHỆ MỚI: BUFFER SCAN)
# ==================================================

def convert_vn_currency(val):
    """Chuyển đổi tiền tệ VN: 14.267.984 -> 14267984"""
    if pd.isna(val): return 0
    s = str(val)
    s = re.sub(r'[^\d.,-]', '', s) 
    # Logic đoán dấu (Ưu tiên: Chấm là hàng nghìn, Phẩy là thập phân)
    if s.count('.') > 1: s = s.replace('.', '') 
    elif '.' in s and ',' in s: s = s.replace('.', '').replace(',', '.') 
    elif ',' in s: s = s.replace(',', '.') 
    elif '.' in s: 
        parts = s.split('.')
        if len(parts) > 1 and len(parts[-1]) == 3: s = s.replace('.', '')
    try: return float(s)
    except: return 0

def force_read_file(file):
    """
    Đọc file vào bộ nhớ -> Convert String -> Tìm Header -> Đọc Pandas
    Cách này tránh lỗi file con trỏ (pointer) và lỗi encoding.
    """
    try:
        # 1. Đọc nội dung file thô (Bytes)
        bytes_data = file.getvalue()
        
        # 2. Cố gắng giải mã thành chữ (String)
        text_data = ""
        encodings = ['utf-8', 'utf-16', 'utf-8-sig', 'latin1', 'cp1252']
        for enc in encodings:
            try:
                text_data = bytes_data.decode(enc)
                break
            except: continue
            
        if not text_data: return None, "Lỗi Encoding (Không đọc được chữ)"

        # 3. Tạo bộ nhớ đệm (StringIO) để Pandas đọc
        # (Giả lập file text đã sạch sẽ)
        
        # 4. Quét tìm dòng tiêu đề
        lines = text_data.splitlines()
        header_idx = 0
        keywords = ["tổng doanh số (vnd)", "mã đơn hàng", "chi phí", "tên dịch vụ hiển thị", "ngày đặt hàng", "tổng tiền", "doanh thu"]
        
        for i, line in enumerate(lines[:50]): # Quét 50 dòng đầu
            if any(k in line.lower() for k in keywords):
                header_idx = i
                break
        
        # 5. Đọc Pandas từ bộ nhớ đệm
        # Dùng engine='python' để tự xử lý các dòng bị lỗi (bad lines)
        buffer = io.StringIO(text_data)
        
        try:
            # Nếu là CSV
            df = pd.read_csv(buffer, header=header_idx, sep=None, engine='python')
        except:
            # Nếu thất bại, thử đọc như Excel (nếu người dùng đổi đuôi)
            buffer = io.BytesIO(bytes_data)
            df = pd.read_excel(buffer, header=header_idx)
            
        return df, "OK"
        
    except Exception as e:
        return None, str(e)

def process_shopee_files(revenue_file, ads_file):
    total_rev = 0; total_ads = 0; logs = []

    # --- XỬ LÝ DOANH THU ---
    if revenue_file:
        df, status = force_read_file(revenue_file)
        if df is not None:
            logs.append(f"✅ File Doanh Thu: Đọc thành công ({len(df)} dòng)")
            
            # Tìm cột tiền
            col_target = None
            kw_rev = ["tổng doanh số (vnd)", "doanh số (vnd)", "tổng tiền", "doanh thu"]
            for col in df.columns:
                if any(k in str(col).lower() for k in kw_rev):
                    col_target = col; break
            
            if col_target:
                logs.append(f"👉 Cột tiền: {col_target}")
                # Lọc bỏ dòng tổng (thường Shopee có dòng tổng ở đầu hoặc cuối)
                # Logic: Nếu file có nhiều dòng, ta cộng tổng các dòng con, hoặc lấy dòng tổng nếu có
                # Để an toàn: Ta tính tổng cột, nhưng nếu kết quả quá lớn (gấp đôi thực tế), ta chia đôi?
                # Cách tốt nhất với Shopee: Convert hết và cộng lại.
                # Tuy nhiên, file Shopee Stats có dòng 1 là Tổng cả tuần, các dòng sau là từng ngày.
                # Mẹo: Nếu dòng đầu tiên chứa khoảng thời gian (vd: "29-12..."), bỏ qua nó.
                
                df['clean_money'] = df[col_target].apply(convert_vn_currency)
                
                # Kiểm tra nếu dòng đầu tiên > tổng các dòng còn lại (dấu hiệu dòng Tổng)
                first_val = df['clean_money'].iloc[0]
                rest_sum = df['clean_money'].iloc[1:].sum()
                
                # Nếu dòng 1 xấp xỉ tổng còn lại -> Chỉ lấy dòng 1 (là dòng Tổng tuần)
                if len(df) > 1 and abs(first_val - rest_sum) < (first_val * 0.1): # Sai số 10%
                    total_rev = first_val
                    logs.append("ℹ️ Phát hiện dòng Tổng ở đầu. Đã lấy giá trị này.")
                else:
                    total_rev = df['clean_money'].sum()
            else:
                logs.append(f"⚠️ Không thấy cột tiền. Cột có: {list(df.columns)}")
        else: logs.append(f"❌ Lỗi Doanh Thu: {status}")

    # --- XỬ LÝ ADS ---
    if ads_file:
        df, status = force_read_file(ads_file)
        if df is not None:
            logs.append(f"✅ File Ads: Đọc thành công")
            col_target = None
            kw_ads = ["chi phí", "cost", "tiền chạy"]
            for col in df.columns:
                if any(k in str(col).lower() for k in kw_ads):
                    col_target = col; break
            
            if col_target:
                logs.append(f"👉 Cột chi phí: {col_target}")
                total_ads = df[col_target].apply(convert_vn_currency).sum()
            else: logs.append(f"⚠️ Không thấy cột phí.")
        else: logs.append(f"❌ Lỗi Ads: {status}")

    return total_rev, total_ads, logs

# ==================================================
# 4. GIAO DIỆN CHÍNH
# ==================================================
with st.sidebar:
    st.title("🦅 BCM Cloud v4.1")
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
    st.title("📊 BÁO CÁO KINH DOANH (FORCE MODE)")
    st.info("💡 Hệ thống dùng thuật toán cưỡng chế đọc file để sửa lỗi định dạng.")
    d = st.date_input("Chọn tuần:", datetime.now())
    
    with st.expander("📂 UPLOAD FILE SHOPEE", expanded=True):
        f1 = st.file_uploader("File Doanh Thu (Shop Stats)")
        f2 = st.file_uploader("File Quảng Cáo (Ads)")
        
        if f1 or f2:
            rev, ads, debug_info = process_shopee_files(f1, f2)
            with st.expander("🔍 Nhật Ký Xử Lý (Log)"):
                for l in debug_info: st.write(l)

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
