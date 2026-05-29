import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# ĐỊNH NGHĨA CÁC HÀM PYTHON THỰC TẾ (Hành động của Agent)
# ---------------------------------------------------------------------------
def get_weather(location: str) -> str:
    """Hàm giả lập lấy thời tiết thực tế tại một địa điểm"""
    if "hà nội" in location.lower():
        return "Thời tiết tại Hà Nội hiện tại là 28°C, có mưa rào."
    elif "hồ chí minh" in location.lower() or "hcm" in location.lower():
        return "Thời tiết tại TP.HCM hiện tại là 34°C, trời nắng gắt."
    else:
        return f"Không tìm thấy dữ liệu thời tiết cho {location}."


class AgentModel:
    def __init__(self):
        self.base_url = os.environ.get("URL_host")
        self.api_key = os.environ.get("API_KEY")
        self.available_tools = {}
        self.skills_context = ""
        
        # 🧠 QUẢN LÝ BỘ NHỚ TOÀN CỤC
        self.history_file = "chat_history.json"
        self.messages = [] # Kho lưu trữ chung sẽ được sử dụng xuyên suốt

        # KHỞI CHẠY NHỮNG HÀM KHỞI TẠO NỀN TẢNG
        self.load_markdown_formulas()
        self.load_history_from_file() # 🔥 SỬA LỖI: Phải gọi nạp lịch sử cũ ngay khi bật máy

    def start_running(self):
        """Khởi tạo OpenAI Client kết nối tới Local Server"""
        if self.base_url and self.api_key:
            print(f"🔗 Đang kết nối tới server: {self.base_url}")
            self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        else:
            raise ValueError("Thiếu cấu hình URL_host hoặc API_KEY trong file .env!")
        
    def create_tools(self):
        pass

    def get_system_instruction(self) -> str:
        """Trả về nội dung System Prompt kèm theo các công thức"""
        return (
            "Bạn là Hermes Agent, trợ lý AI thông minh chạy trên nền tảng Gemma.\n"
            "Dưới đây là danh sách các KỸ NĂNG VÀ CÔNG THỨC bạn ĐƯỢC PHÉP SỬ DỤNG để tính toán và trả lời người dùng. "
            "Hãy áp dụng chúng một cách chính xác từng bước một (Step-by-step reasoning):\n\n"
            f"{self.skills_context}\n\n"
            "Yêu cầu: Nếu câu hỏi của người dùng liên quan đến các công thức trên, hãy trích dẫn công thức và hiển thị quá trình tính toán chi tiết.\n"
            "Hãy luôn dựa vào lịch sử hội thoại phía dưới để trò chuyện mạch lạc."
        )

    # ---------------------------------------------------------------------------
    # NẠP FILE SKILLS
    # ---------------------------------------------------------------------------
    def load_markdown_formulas(self):
        """Tự động đọc toàn bộ file .md chứa công thức và gộp thành kho tri thức"""
        skills_dir = "skills"
        if not os.path.exists(skills_dir):
            os.makedirs(skills_dir)
            return

        print("📂 Đang nạp các file công thức kỹ năng (.md)...")
        loaded_skills = []
        
        for filename in os.listdir(skills_dir):
            if filename.endswith(".md"):
                file_path = os.path.join(skills_dir, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                    loaded_skills.append(f"--- BẮT ĐẦU KỸ NĂNG: {filename} ---\n{file_content}\n--- KẾT THÚC KỸ NĂNG ---")
                    print(f"  ✅ Đã nạp công thức từ file: '{filename}'")
        
        self.skills_context = "\n\n".join(loaded_skills)

    # ---------------------------------------------------------------------------
    # MEMORY - LƯU LẠI LỊCH SỬ (.json - Giới hạn 20 cặp gần nhất)
    # ---------------------------------------------------------------------------
    def load_history_from_file(self):
        """Kỹ năng đọc lại file lịch sử cũ (.json) để tái sử dụng"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self.messages = json.load(f)
                
                # Cập nhật lại System Prompt mới nhất (đề phòng bạn sửa đổi file .md công thức)
                if self.messages and self.messages[0]["role"] == "system":
                    self.messages[0]["content"] = self.get_system_instruction()
                
                total_pairs = (len(self.messages) - 1) // 2
                print(f"💾 [Memory] Đã khôi phục thành công {total_pairs} đoạn hội thoại gần nhất từ file JSON!")
            except Exception as e:
                print(f"⚠️ Lỗi khi đọc file lịch sử cũ: {e}. Tiến hành khởi tạo phiên mới.")
                self.reset_memory()
        else:
            self.reset_memory()

    def save_history_to_file(self):
        """Kỹ năng giới hạn 20 đoạn chat gần nhất và ghi đè vào file .json để lưu trữ"""
        try:
            MAX_MESSAGES = 41 # 1 system + 40 câu thoại (20 cặp user/assistant)

            if len(self.messages) > MAX_MESSAGES:
                system_msg = self.messages[0]
                recent_chats = self.messages[-40:] # Cắt lấy 40 tin nhắn mới nhất
                self.messages = [system_msg] + recent_chats
                print(f"✂️ [Memory] Đã tự động tối ưu bộ nhớ, chỉ giữ lại 20 đoạn hội thoại mới nhất.")

            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.messages, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"⚠️ Không thể lưu lịch sử vào file: {e}")

    def reset_memory(self):
        """Khởi tạo lại bộ nhớ trắng"""
        self.messages = [
            {"role": "system", "content": self.get_system_instruction()}
        ]
        self.save_history_to_file()

    def clear_memory_completely(self):
        """Xóa sạch cả bộ nhớ tạm lẫn file .json lưu trên ổ cứng"""
        self.reset_memory()
        print("\n🧹 [Memory] Đã xóa sạch lịch sử trò chuyện cũ trên cả hệ thống và file!") 

    def chat(self, message):
        pass


class Gemma_4(AgentModel):
    def __init__(self):
        super().__init__()
        self.available_tools = {
            "get_weather": get_weather
        }
        self.create_tools()
        self.start_running()

    def create_tools(self):
        super().create_tools()
        self.tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Lấy thông tin thời tiết hiện tại của một tỉnh hoặc thành phố cụ thể.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "Tên thành phố hoặc tỉnh thành, ví dụ: Hà Nội, TP.HCM",
                            }
                        },
                        "required": ["location"],
                    },
                },
            }
        ]

    def chat(self, message):
        # 🔥 SỬA LỖI ĐẶC BIỆT QUAN TRỌNG:
        # Không dùng biến 'messages = [...]' cục bộ nữa, mà đẩy trực tiếp vào kho lưu trữ 'self.messages'
        self.messages.append({"role": "user", "content": message})

        try:
            # LƯỢT 1: Gửi toàn bộ kho lịch sử tích lũy kèm mô tả Tools cho Gemma
            response = self.client.chat.completions.create(
                model="local-model",
                messages=self.messages, # Thay đổi ở đây
                tools=self.tools_schema,
                tool_choice="auto"
            )        
            
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            # Kiểm tra xem Gemma có yêu cầu gọi hàm (Function Call) không
            if tool_calls:
                print("🤖 [Hermes] Mô hình quyết định gọi công cụ ngoại vi...")
                
                # Lưu tin nhắn yêu cầu gọi hàm của Model vào lịch sử hệ thống
                self.messages.append(response_message)

                # Thực thi từng hàm mà Model yêu cầu
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    print(f"⚙️ Đang thực thi hàm: `{function_name}` với tham số: {function_args}")
                    
                    if function_name in self.available_tools:
                        tool_output = self.available_tools[function_name](**function_args)
                    else:
                        tool_output = f"Lỗi: Không tìm thấy hàm {function_name}"

                    # Gửi kết quả thực thi của hàm vào kho lịch sử tin nhắn chung
                    self.messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_output,
                    })

                # LƯỢT 2: Gửi lại toàn bộ lịch sử (gồm kết quả của Tool) để Gemma tổng hợp câu trả lời
                final_response = self.client.chat.completions.create(
                    model="local-model",
                    messages=self.messages, # Thay đổi ở đây
                )
                
                ai_final_reply = final_response.choices[0].message.content
                
                # Nạp câu trả lời tổng hợp cuối cùng của AI vào kho lưu trữ
                self.messages.append({"role": "assistant", "content": ai_final_reply})
                
                # 🔥 GỌI HÀM LƯU: Ghi lại toàn bộ dữ liệu vừa diễn ra vào file cứng
                self.save_history_to_file()
                
                return ai_final_reply
            else:
                # Nếu không cần gọi tool, lưu câu trả lời thông thường của AI vào kho dữ liệu
                ai_reply = response_message.content
                self.messages.append({"role": "assistant", "content": ai_reply})
                
                # 🔥 GỌI HÀM LƯU: Ghi lại dữ liệu khi không gọi Tool
                self.save_history_to_file()
                
                return ai_reply

        except Exception as e:
            # Nếu xảy ra lỗi kết nối đột ngột, xóa tin nhắn user vừa gõ để tránh hỏng logic lịch sử
            if self.messages and self.messages[-1]["role"] == "user":
                self.messages.pop()
            return f"Lỗi xử lý hệ thống: {str(e)}"


if __name__ == "__main__":
    Agent = Gemma_4()
    print("✨ Hermes Agent đã sẵn sàng! (Gõ 'clear' để xóa lịch sử, 'q' để thoát) ✨\n")
    print("-" * 50)
    
    while True:
        query = input("User: ")
        
        if query.strip().lower() in ['q', 'exit', 'quit']:
            print("\n🤖 [Hermes] Tạm biệt bạn! Hệ thống đang đóng...")
            break
            
        if query.strip().lower() == 'clear':
            Agent.clear_memory_completely()
            continue
            
        if not query.strip():
            continue
            
        print("Hermes đang suy nghĩ...")
        answer = Agent.chat(query)
        
        print(f"\nHermes: {answer}")
        print("-" * 50)