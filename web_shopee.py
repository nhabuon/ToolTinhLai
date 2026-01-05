import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document

# ==============================================================================
# 1. CẤU HÌNH HỆ THỐNG & API
# ==============================================================================
st.set_page_config(page_title="BCM Cloud v3.6 - MIT Corp", page_icon="🦅", layout="wide")

# Lấy API Key từ Secrets
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except:
    st.error("⚠️ Chưa cấu hình GOOGLE_API_KEY trong Secrets!")
    st.stop()

# Cấu hình Model (Dùng bản 1.5 Pro hoặc bản mới nhất Sếp muốn)
# Lưu ý: Sếp có thể đổi tên model thành 'gemini-1.5-flash' nếu muốn tốc độ nhanh hơn
MODEL_CONFIG = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
}
model = genai.GenerativeModel('gemini-3-pro-preview', generation_config=MODEL_CONFIG)

# ==============================================================================
# 2. HÀM XỬ LÝ FILE (KNOWLEDGE BASE)
# ==============================================================================
def get_file_content(uploaded_file):
    """Đọc nội dung file PDF, DOCX, TXT"""
    text = ""
    try:
        if uploaded_file.name.endswith(".pdf"):
            pdf_reader = PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        elif uploaded_file.name.endswith(".docx"):
            doc = Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif uploaded_file.name.endswith(".txt"):
            text = uploaded_file.read().decode("utf-8")
    except Exception as e:
        st.toast(f"Lỗi đọc file {uploaded_file.name}: {e}")
    return text

# ==============================================================================
# 3. GIAO DIỆN SIDEBAR (MENU & UPLOAD)
# ==============================================================================
with st.sidebar:
    st.title("🦅 BCM Cloud v3.6")
    st.markdown("---")
    
    # --- CHỌN NHÂN SỰ ---
    st.subheader("👥 Chọn Nhân Sự")
    role = st.radio(
        "AI hoạt động:",
        ["🔴 An (RCM Engineer)", "🟡 Sư (Advisor)"],
        captions=["Kỹ thuật & Thực thi", "Chiến lược & Binh pháp"]
    )
    
    st.markdown("---")
    
    # --- KHO TRI THỨC (UPLOAD) ---
    st.subheader("📂 Kho Tri Thức (RAG)")
    uploaded_files = st.file_uploader(
        "Nạp tài liệu (PDF, Word):", 
        accept_multiple_files=True,
        type=['pdf', 'docx', 'txt']
    )
    
    # Xử lý file ngay khi upload
    knowledge_context = ""
    if uploaded_files:
        with st.status("Đang học dữ liệu...", expanded=True) as status:
            for file in uploaded_files:
                content = get_file_content(file)
                if content:
                    knowledge_context += f"\n--- TÀI LIỆU: {file.name} ---\n{content}\n"
                    st.write(f"✅ Đã hiểu: {file.name}")
            status.update(label="Đã nạp xong kiến thức!", state="complete", expanded=False)
            
    st.markdown("---")
    st.info("💡 **Ghi chú:**\n- **An:** Tập trung vào thông số, kỹ thuật, code.\n- **Sư:** Tập trung vào thị trường, đối thủ, chiến lược.")

# ==============================================================================
# 4. GIAO DIỆN CHAT CHÍNH
# ==============================================================================

st.header("Phòng Họp Chiến Lược (Dual Core)")

# Khởi tạo lịch sử chat nếu chưa có
if "messages" not in st.session_state:
    st.session_state.messages = []

# Hiển thị lịch sử chat cũ
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Xử lý khi Sếp nhập câu hỏi
if prompt := st.chat_input("Ra lệnh cho hệ thống..."):
    # 1. Hiển thị câu hỏi của Sếp
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Xây dựng Prompt (Lời dẫn) tùy theo vai trò
    system_instruction = ""
    
    if "An (RCM Engineer)" in role:
        # Prompt cho AN
        system_instruction = f"""
        Bạn là An - Kỹ sư AI và trợ lý kỹ thuật đắc lực của Sếp Lâm (MIT Corp).
        Phong cách: Trung thành, Cụ thể, Chi tiết, Kỹ thuật, Thực tế.
        
        Dữ liệu tham khảo nội bộ (nếu có):
        {knowledge_context}
        
        Nhiệm vụ: Trả lời câu hỏi dựa trên dữ liệu (nếu liên quan) và kiến thức kỹ thuật.
        Nếu có số liệu trong file, hãy trích dẫn chính xác.
        """
    else:
        # Prompt cho SƯ
        system_instruction = f"""
        Bạn là Sư (Advisor) - Cố vấn chiến lược cấp cao của Shop MIT.
        Phong cách: Thâm sâu, Chiến lược, Phân tích thị trường, Tâm lý khách hàng (Sun Tzu style).
        
        Dữ liệu tham khảo nội bộ (nếu có):
        {knowledge_context}
        
        Nhiệm vụ: Phân tích vấn đề dưới góc độ KINH DOANH & CẠNH TRANH.
        Tuyệt đối không đi sâu vào chi tiết kỹ thuật (trừ khi nó là USP bán hàng).
        Hãy đưa ra lời khuyên hành động cụ thể để tăng doanh thu hoặc hạ gục đối thủ.
        """

    full_prompt = f"{system_instruction}\n\nCâu hỏi của Sếp: {prompt}"

    # 3. Gọi AI xử lý
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        try:
            # Stream response (Hiển thị chữ chạy chạy cho ngầu)
            response = model.generate_content(full_prompt, stream=True)
            full_response = ""
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            
            # Lưu câu trả lời vào lịch sử
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"Lỗi kết nối AI: {e}")
