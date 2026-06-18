import os
import json
import re
import requests
from pathlib import Path

# --- CẤU HÌNH HỆ THỐNG ---
# OLLAMA_URL = "http://localhost:11434/api/chat"
# MODEL_NAME = "gemma4:31b" # Hoặc "gemma4:12b" tùy thuộc vào cấu hình máy của bạn
SKILLS_DIR = Path("./skills")

# --- BƯỚC 1: TỰ ĐỘNG TẠO CÁC FILE SKILL `.md` MẪU (Để chạy thử nghiệm) ---
def setup_mock_skills():
    """Tạo thư mục và các file kỹ năng Markdown mẫu để kiểm thử"""
    SKILLS_DIR.mkdir(exist_ok=True)
    
    # Kỹ năng 1: Giải toán nâng cao
    math_skill = """# SKILL: Advanced Math Solver
Description: Dùng để giải các biểu thức toán học phức tạp hoặc thực hiện tính toán.

## Prompt & Examples:
Bạn là một chuyên gia toán học. Khi giải toán, hãy trình bày từng bước một cách khoa học.
Ví dụ:
User: Tính 15 * 4 + 20
Thought: Cần thực hiện phép nhân trước, phép cộng sau.
Result: 15 * 4 = 60. Sau đó 60 + 20 = 80.
Final Answer: 80
"""
    
    # Kỹ năng 2: Tìm kiếm thời gian thực
    search_skill = """# SKILL: Web Search Engine
Description: Dùng để tìm kiếm thông tin mới nhất trên Internet, tin tức, sự kiện vừa diễn ra.

## Prompt & Examples:
Bạn là một trợ lý thông tin có khả năng duyệt web. Hãy tóm tắt thông tin tìm được một cách khách quan nhất.
Ví dụ:
User: Thời tiết hôm nay thế nào?
Result: Hệ thống ghi nhận nhiệt độ trung bình là 28 độ C, trời có mây rải rác.
Final Answer: Thời tiết hôm nay mát mẻ, nhiệt độ khoảng 28 độ C, thích hợp cho hoạt động ngoài trời.
"""

    with open(SKILLS_DIR / "math_solver.md", "w", encoding="utf-8") as f:
        f.write(math_skill)
    with open(SKILLS_DIR / "web_search.md", "w", encoding="utf-8") as f:
        f.write(search_skill)
    print("📢 [Hệ thống]: Đã khởi tạo các file kỹ năng mẫu (.md) trong thư mục /skills\n")


# --- BƯỚC 2: QUÉT VÀ TRÍCH XUẤT THÔNG TIN SKILLS (Không load toàn bộ nội dung) ---
def scan_skills_catalog():
    """Quét thư mục skills/ và chỉ lấy tên file + dòng mô tả (Description) để tiết kiệm Context"""
    catalog = {}
    
    if not SKILLS_DIR.exists():
        return catalog
        
    for file_path in SKILLS_DIR.glob("*.md"):
        skill_id = file_path.stem # Lấy tên file làm ID (Ví dụ: math_solver)
        description = "No description provided."
        
        # Chỉ đọc vài dòng đầu của file để tìm dòng Description, không load hết file
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("Description:"):
                    description = line.replace("Description:", "").strip()
                    break
                    
        catalog[skill_id] = {
            "file_path": str(file_path),
            "description": description
        }
    return catalog


# --- BƯỚC 3: GỬI YÊU CẦU ĐẾN GEMMA 4 ---
def query_gemma(messages):
    """Gửi danh sách tin nhắn tới API Ollama chứa Gemma 4"""
    try:
        payload = {
            "model": MODEL_NAME,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.1} # Nhiệt độ thấp giúp mô hình chọn chính xác hơn
        }
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        return response.json()['message']['content']
    except Exception as e:
        return f"ERROR_CONNECTION: Không thể kết nối tới Ollama. {str(e)}"


# --- BƯỚC 4: VÒNG LẶP ĐIỀU PHỐI DYNAMIC LOAD ---
def run_dynamic_agent(user_query: str):
    print(f"❓ [Yêu cầu của bạn]: {user_query}")
    
    # 1. Quét danh mục kỹ năng hiện có
    catalog = scan_skills_catalog()
    if not catalog:
        print("❌ Không tìm thấy kỹ năng nào trong thư mục /skills.")
        return

    # 2. Xây dựng danh mục tối giản để gửi cho Router Agent
    catalog_summary = ""
    for skill_id, info in catalog.items():
        catalog_summary += f"- Kỹ năng: `{skill_id}` | Mô tả: {info['description']}\n"

    # 3. Định nghĩa System Prompt cho vai trò định tuyến (Router)
    router_prompt = f"""You are a Router Agent powered by Gemma 4. Your only job is to analyze the user's request and select the single best skill from the list below to solve it.

Available Skills:
{catalog_summary}

You MUST reply with the exact skill ID in this JSON format:
```json
{{
  "selected_skill": "skill_id_here"
}}
```
Do not output anything else.
"""

    messages = [
        {"role": "system", "content": router_prompt},
        {"role": "user", "content": user_query}
    ]

    print("🧠 [Harness]: Đang hỏi Gemma 4 xem nên dùng kỹ năng nào...")
    router_response = query_gemma(messages)
    
    # Trích xuất skill ID được chọn từ JSON của Gemma 4
    selected_skill = None
    json_match = re.search(r"```json\s*(.*?)\s*```", router_response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            selected_skill = data.get("selected_skill")
        except Exception:
            pass

    if not selected_skill or selected_skill not in catalog:
        print(f"⚠️ [Harness]: Gemma 4 không chọn được kỹ năng phù hợp (Kết quả: {router_response}). Sử dụng chế độ mặc định.")
        # Xử lý fallback nếu không chọn được skill
        return

    print(f"🎯 [Harness]: Gemma 4 đã quyết định chọn kỹ năng: '{selected_skill}'")
    
    # 4. TIẾN HÀNH NẠP ĐỘNG (DYNAMIC LOADING)
    # Lúc này mới thực sự đọc toàn bộ nội dung chi tiết của file .md được chọn
    skill_file_path = catalog[selected_skill]["file_path"]
    print(f"📖 [Harness]: Đang đọc nội dung chi tiết của file '{skill_file_path}' vào bộ nhớ...")
    
    with open(skill_file_path, "r", encoding="utf-8") as f:
        full_skill_prompt = f.read()

    # 5. Thực thi nhiệm vụ với Prompt chi tiết vừa được nạp
    execution_prompt = f"""Bạn có một kỹ năng đặc biệt vừa được kích hoạt để giải quyết yêu cầu của người dùng. Hãy sử dụng tài liệu hướng dẫn của kỹ năng này để xử lý.

Tài liệu hướng dẫn kỹ năng:
{full_skill_prompt}

Yêu cầu cần giải quyết: {user_query}
"""
    
    execution_messages = [
        {"role": "user", "content": execution_prompt}
    ]
    
    print("⚡ [Harness]: Đang chạy kỹ năng đã nạp để xử lý yêu cầu...")
    final_output = query_gemma(execution_messages)
    
    print("\n================== KẾT QUẢ CUỐI CÙNG ==================")
    print(final_output)
    print("=======================================================\n")


# --- KHỞI CHẠY ---
if __name__ == "__main__":
    # Khởi tạo dữ liệu thử nghiệm
    setup_mock_skills()
    
    # Thử nghiệm 1: Yêu cầu kích hoạt kỹ năng Toán
    query_1 = "Hãy tính giúp tôi phép tính sau: 125 nhân cho 8 rồi cộng với 1000"
    run_dynamic_agent(query_1)
    
    # Thử nghiệm 2: Yêu cầu kích hoạt kỹ năng Tìm kiếm
    query_2 = "Sự kiện công nghệ nổi bật nào diễn ra vào năm 2026?"
    run_dynamic_agent(query_2)