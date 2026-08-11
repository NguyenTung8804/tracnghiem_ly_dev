import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict
#------------------Thu_viện_gửi_email-------------------------------
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
#--------------End----Thu_viện_gửi_email---------------------------------
#------------------Thu_viện_đính_kèm_email------------------------------
import os
import pdfkit
from email.mime.base import MIMEBase
from email import encoders
#------------------Thu_viện_đính_kèm_email------------------------------

app = FastAPI()

# ---------------- CẤU HÌNH GỬI EMAIL MIỄN PHÍ ----------------
SMTP_SERVER = "smtp.gmail.com"
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
class EmailSubmit(BaseModel):
    name: str
    email: str
    result: dict

@app.post("/api/send-result-email")
async def send_result_email(data: EmailSubmit):
    pdf_filename = f"KetQua_{data.name.replace(' ', '_')}.pdf"
    try:
        r = data.result
        questions_list = r.get("questions", [])
      #-----------------------------------------------------
      # --- ĐOẠN CODE NÂNG CẤP GIAO DIỆN PDF SANG TRỌNG TRONG MAIN.PY ---
        questions_html = ""
        for index, q in enumerate(questions_list, 1):
            user_ans = q.get("user_answer", "Không trả lời")
            correct_ans = q.get("correct_answer", "")
            is_correct = "✔ Đúng" in user_ans or user_ans == correct_ans
            bg_badge = "#e6f4ea" if is_correct else "#fce8e6"
            text_badge = "#137333" if is_correct else "#c5221f"
            
            # HTML cho từng câu hỏi với bảng so sánh đáp án
            questions_html += f"""
            <div class="question-card">
                <div class="question-text"><strong>Câu {index}:</strong> {q.get("question_text", "")}</div>
                <table class="ans-table">
                    <tr>
                        <td width="50%">
                            <div class="ans-label">Đáp án của bạn:</div>
                            <div class="ans-value" style="background-color: {bg_badge}; color: {text_badge};">{user_ans}</div>
                        </td>
                        <td width="50%">
                            <div class="ans-label">Đáp án đúng:</div>
                            <div class="ans-value" style="background-color: #e8f0fe; color: #1a73e8;">{correct_ans}</div>
                        </td>
                    </tr>
                </table>
                {f'<div class="explanation-box"><strong>💡 Giải thích:</strong> {q.get("explanation")}</div>' if q.get("explanation") else ''}
            </div>"""

        # Cấu hình Layout HTML/CSS chi tiết cho file PDF
        pdf_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{ size: A4; margin: 20mm 15mm; }}
                body {{ font-family: sans-serif; color: #202124; line-height: 1.6; }}
                .brand-header {{ text-align: center; border-bottom: 3px double #1a73e8; padding-bottom: 10px; }}
                .summary-card {{ background: #f8f9fa; border: 1px solid #dadce0; padding: 15px; border-radius: 8px; }}
                .question-card {{ border: 1px solid #dadce0; padding: 15px; margin-bottom: 15px; page-break-inside: avoid; }}
                .ans-table {{ width: 100%; border-collapse: collapse; }}
                .ans-value {{ padding: 8px; border-radius: 4px; font-weight: bold; text-align: center; }}
                .explanation-box {{ margin-top: 10px; padding: 10px; background-color: #fdf6e2; border-left: 3px solid #f57c00; }}
            </style>
        </head>
        <body>
            <div class="brand-header"><h2>VIETDRAGON LEARNING CENTER</h2></div>
            <div class="summary-card">
                <p><strong>Học sinh:</strong> {data.name}</p>
                <p><strong>Tổng điểm:</strong> {r.get("total_score", 0)}/10</p>
            </div>
            <h3>CHI TIẾT BÀI THI</h3>
            {questions_html}
        </body>
        </html>"""  
     # --END- ĐOẠN CODE NÂNG CẤP GIAO DIỆN PDF SANG TRỌNG TRONG MAIN.PY ---      
        import pdfkit
        options = {'encoding': "UTF-8", 'javascript-delay': '2500', 'no-outline': None}
        pdfkit.from_string(pdf_html, pdf_filename, options=options)
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        from email.header import Header
        import aiosmtplib
        import unicodedata
        msg = MIMEMultipart('mixed')
        msg['From'] = f"VietDragon <{SENDER_EMAIL}>"
        msg['To'] = data.email
        msg['Subject'] = Header(f"KẾT QUẢ THI - {data.name}", 'utf-8').encode()
        msg.attach(MIMEText("Chào bạn, vui lòng xem tệp đính kèm.", 'plain', 'utf-8'))
        with open(pdf_filename, "rb") as f:
            part = MIMEBase("application", "pdf")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        safe_filename = unicodedata.normalize('NFKD', pdf_filename).encode('ascii', 'ignore').decode('utf-8')
        part.add_header("Content-Disposition", f'attachment; filename="{safe_filename}"')
        msg.attach(part)
        await aiosmtplib.send(msg, hostname=SMTP_SERVER, port=SMTP_PORT, username=SENDER_EMAIL, password=SENDER_PASSWORD, start_tls=True)
        return {"success": True, "message": "Đã gửi email thành công!"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        import os
        if os.path.exists(pdf_filename):
            os.remove(pdf_filename)
# ------End---------- ĐỒNG BỘ DỮ LIỆU VÀ XỬ LÝ GỬI EMAIL MÔN VẬT LÝ ----------------

