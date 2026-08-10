import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict
#-------------------------------------------------
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


app = FastAPI()

# ---------------- CẤU HÌNH GỬI EMAIL MIỄN PHÍ ----------------
SMTP_SERVER = "://gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "tracnghiemonlinevietdragon@gmail.com"
SENDER_PASSWORD = "iisogmecxfzjufnd"
# ---------End------- CẤU HÌNH GỬI EMAIL MIỄN PHÍ ----------------

# Cấu hình Static và Jinja2 Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def load_filtered_questions(khoi: int, loai: str, nam: int, de_so: int):
    try:
        with open("database.json", "r", encoding="utf-8") as f:
            all_questions = json.load(f)
        return [q for q in all_questions if q.get("khoi_lop") == khoi and q.get("loai_de") == loai and q.get("nam_hoc") == nam and q.get("de_so") == de_so]
    except Exception:
        return []
@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse(request=request, name="home.html", context={})

@app.get("/thi", response_class=HTMLResponse)
async def read_item(request: Request, de_so: int = 1):
    questions = load_filtered_questions(khoi=12, loai="Thi Dai Hoc", nam=2026, de_so=de_so)
    secure_questions = []
    
    for q in questions:
        q_secure = q.copy()
        # 🎯 BẢO MẬT: Xóa bỏ đáp án đúng và giải chi tiết trước khi gửi xuống HTML mẫu
        if "dap_an_dung" in q_secure:
            del q_secure["dap_an_dung"]
        if "giai_chi_tiet" in q_secure:
            del q_secure["giai_chi_tiet"]
        secure_questions.append(q_secure)
        
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"questions": secure_questions, "de_so": de_so}
    )
class ExamSubmit(BaseModel):
    answers: Dict[str, str]
    de_so: int

@app.post("/api/submit")
async def submit_exam(data: ExamSubmit):
    questions = load_filtered_questions(khoi=12, loai="Thi Dai Hoc", nam=2026, de_so=data.de_so)
    student_answers = data.answers
    
    total_score = 0.0
    score_p1 = 0
    score_p2 = 0
    score_p3 = 0
    total_attempted = 0  # Đếm tổng số câu học sinh thực sự làm bài toàn đề thi
    detailed_results = []
    
    for q in questions:
        q_id_str = str(q["id"])
        is_correct_block = False
        sub_feedback = {}
        
        # 1. CHẤM ĐIỂM PHẦN II (TRẮC NGHIỆM ĐÚNG/SAI LŨY TIẾN THEO Ý - CHIA NHỎ ĐIỂM 1/4)
        if q.get("cac_lua_chon") == "Đúng, Sai":
            raw_db_ans = str(q["dap_an_dung"]).replace(" ", "").split(",")
            if len(raw_db_ans) == 1 and len(raw_db_ans) == 4:
                raw_db_ans = list(raw_db_ans)
                
            correct_sub_count = 0
            has_attempted_p2 = False
            sub_keys = ['a', 'b', 'c', 'd']
            
            for idx, sub in enumerate(sub_keys):
                radio_name = f"q_{q['id']}_{sub}"
                chosen_sub = student_answers.get(radio_name, "Chưa chọn").strip().upper()
                
                if chosen_sub != "CHƯA CHỌN":
                    has_attempted_p2 = True
                
                if chosen_sub == "D": 
                    chosen_sub = "Đ"
                correct_sub_ans = raw_db_ans[idx].strip().upper() if idx < len(raw_db_ans) else "Đ"
                if correct_sub_ans == "D": 
                    correct_sub_ans = "Đ"
                    
                is_sub_correct = (chosen_sub == correct_sub_ans)
                if is_sub_correct:
                    correct_sub_count += 1
                    
                sub_feedback[sub] = {
                    "chosen": chosen_sub,
                    "correct": correct_sub_ans,
                    "is_correct": is_sub_correct
                }
            
            if has_attempted_p2:
                total_attempted += 1
                
            # THUẬT TOÁN QUY ĐỔI 1/4 ĐIỂM: Thang điểm chuẩn của câu hỏi Đúng/Sai là 1.0 điểm.
            # Đúng 1 ý được 0.25 điểm hệ 10 gộp tích lũy trực tiếp vào tổng bài.
            p2_points = correct_sub_count * 0.25
            total_score += p2_points
            
            if correct_sub_count == 4:
                is_correct_block = True
                score_p2 += 1
                
        # 2. CHẤM ĐIỂM ĐỒNG BỘ CHO PHẦN I VÀ PHẦN III
        else:
            chosen = student_answers.get(q_id_str, "Chưa chọn").strip()
            db_ans = str(q["dap_an_dung"]).strip()
            
            if chosen != "Chưa chọn":
                total_attempted += 1
                
            # Trắc nghiệm chọn 1 đáp án Phần I (Mỗi câu đúng = 0.25 điểm)
            if q.get("cac_lua_chon") != "Đúng, Sai" and "Điền số" not in str(q.get("cac_lua_chon")):
                chosen = chosen.upper()
                db_ans = db_ans.upper()
                is_correct_block = (chosen == db_ans)
                if is_correct_block:
                    score_p1 += 1
                    total_score += 0.25
            else:
                # Trắc nghiệm điền số trả lời ngắn Phan III (Mỗi câu đúng = 0.5 điểm)
                is_correct_block = (chosen == db_ans)
                if is_correct_block:
                    score_p3 += 1
                    total_score += 0.5
                    
        detailed_results.append({
            "id": q["id"],
            "noi_dung": q["noi_dung"],
            "dap_an_dung": str(q["dap_an_dung"]),
            "is_correct": is_correct_block,
            "giai_chi_tiet": q["giai_chi_tiet"],
            "sub_feedback": sub_feedback
        })
        
    return {
        "total_score": round(total_score, 2),
        "score_p1": score_p1,
        "score_p2": score_p2,
        "score_p3": score_p3,
        "total_attempted": total_attempted,
        "total_questions": len(questions),
        "details": detailed_results
    }

# ---------------- ĐỒNG BỘ DỮ LIỆU VÀ XỬ LÝ GỬI EMAIL MÔN VẬT LÝ ----------------
# ---------------- ĐỒNG BỘ DỮ LIỆU VÀ XỬ LÝ GỬI EMAIL MÔN VẬT LÝ ----------------
# ---------------- ĐỒNG BỘ DỮ LIỆU VÀ XỬ LÝ GỬI EMAIL MÔN VẬT LÝ ----------------
class EmailSubmit(BaseModel):
    name: str
    email: str
    result: dict

@app.post("/api/send-result-email")
async def send_result_email(data: EmailSubmit):
    try:
        student_name = data.name
        student_email = data.email
        res_data = data.result

        total_score = res_data.get("total_score", 0)
        total_attempted = res_data.get("total_attempted", 0)
        total_questions = res_data.get("total_questions", 33)
        score_p1 = res_data.get("score_p1", 0)
        score_p2 = res_data.get("score_p2", 0)
        score_p3 = res_data.get("score_p3", 0)

        # Thiết lập tiêu đề và cấu trúc bức thư gửi đi
        msg = MIMEMultipart('alternative')
        msg['From'] = f"VietDragon Learning Center <{SENDER_EMAIL}>"
        msg['To'] = student_email
        msg['Subject'] = f"📋 KẾT QUẢ BÀI THI VẬT LÝ - HỌC SINH: {student_name.upper()}"

        # Biên soạn nội dung bức thư định dạng HTML hiển thị trên điện thoại
        html_content = f"""
        <html>
        <body style="font-family: 'Times New Roman', serif; line-height: 1.6; color: #2d3748; padding: 20px; background-color: #f7fafc;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 10px; padding: 25px; background-color: #ffffff; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                <h2 style="color: #2b6cb0; text-align: center; border-bottom: 2px solid #2b6cb0; padding-bottom: 12px; margin-top: 0; font-size: 24px;">VIETDRAGON LEARNING CENTER</h2>
                <p style="font-size: 16px;">Chào <strong>{student_name}</strong>,</p>
                <p style="font-size: 16px;">Hệ thống đã ghi nhận và hoàn tất chấm điểm bài thi thử trắc nghiệm môn <strong>Vật Lý</strong> của bạn. Dưới đây là thông tin chi tiết bảng điểm:</p>
                
                <div style="background-color: #ebf8ff; border-left: 4px solid #3182ce; padding: 15px; margin: 20px 0; border-radius: 4px;">
                    <p style="font-size: 20px; margin: 0; font-weight: bold; color: #2b6cb0;">🏅 TỔNG ĐIỂM QUY ĐỔI HỆ 10: <span style="font-size: 26px; color: #e53e3e;">{total_score}</span> / 10 điểm</p>
                </div>

                <p style="font-size: 16px; margin-bottom: 8px;"><strong>💡 Thống kê ma trận số lượng câu làm được:</strong></p>
                <ul style="padding-left: 20px; font-size: 15px; list-style-type: none; line-height: 1.8;">
                    <li style="margin-bottom: 5px;">• <strong>Tổng số câu đã thực hiện làm:</strong> <span style="font-weight: bold; color: #3182ce;">{total_attempted}</span> / {total_questions} câu toàn bài</li>
                    <li style="margin-bottom: 5px;">• Số câu trả lời đúng Phần I: <span style="color: #38a169; font-weight: bold;">{score_p1}</span> câu</li>
                    <li style="margin-bottom: 5px;">• Số câu đúng tuyệt đối Phần II: <span style="color: #38a169; font-weight: bold;">{score_p2}</span> câu</li>
                    <li style="margin-bottom: 5px;">• Số câu trả lời đúng Phần III: <span style="color: #38a169; font-weight: bold;">{score_p3}</span> câu</li>
                </ul>

                <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 25px 0;">
                <p style="font-size: 13px; color: #a0aec0; text-align: center; margin-bottom: 0;">Đây là thư thông báo tự động từ hệ thống thi trắc nghiệm trực tuyến VietDragon. Vui lòng không trả lời thư này.</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        # Kích hoạt gửi email bất đồng bộ qua aiosmtplib
        await aiosmtplib.send(
            msg,
            hostname=SMTP_SERVER,
            port=SMTP_PORT,
            username=SENDER_EMAIL,
            password=SENDER_PASSWORD,
            start_tls=True
        )

        return {"success": True, "message": "Email đã được gửi thành công!"}

    except Exception as e:
        return {"success": False, "message": str(e)}
# ------End---------- ĐỒNG BỘ DỮ LIỆU VÀ XỬ LÝ GỬI EMAIL MÔN VẬT LÝ ----------------

