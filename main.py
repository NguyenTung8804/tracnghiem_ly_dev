import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict
#-----------Thu_viện_gửi_email-----------------------------------------
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
#-----------End----Thu_viện_gửi_email----------------------------------
#-----------Thu_viện_đính_kèm_email------------------------------------
import os
import pdfkit
from email.mime.base import MIMEBase
from email import encoders
import asyncio       # Dòng thêm mới 1
import unicodedata   # Dòng thêm mới 2
from email.header import Header # Dòng thêm mới 3
#-----------Thu_viện_đính_kèm_email------------------------------------

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
            "question_text": q["noi_dung"],
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

# -------- ĐỒNG BỘ DỮ LIỆU VÀ XỬ LÝ GỬI EMAIL MÔN VẬT LÝ ----------------
class EmailSubmit(BaseModel):
    name: str
    email: str
    result: dict
#=======================================================================
@app.post("/api/send-result-email")
async def send_result_email(data: EmailSubmit):
    pdf_filename = f"KetQua_{data.name.replace(' ', '_')}.pdf"
    
    try:
        r = data.result
        questions_list = r.get("questions", [])
        questions_html = ""
        last_part = ""
        
        # ──────── THUẬT TOÁN ĐỒNG BỘ LOCAL MATH INTERPRETER SANG PYTHON ────────
        # --- CODE BACKEND ĐỒNG BỘ RÚT GỌN - CHỐNG BỊ VỠ LAYOUT ---
        # --- BỘ LỌC ĐA NĂNG ĐỒNG BỘ CÔNG THỨC TOÁN CHO TOÀN BỘ CÁC PHẦN ---        
        for index, q in enumerate(questions_list, 1):
            current_part = q.get("part_name", "Chi tiết bài làm")
            if current_part != last_part:
                last_part = current_part
                questions_html += f'<div class="part-header-box"><strong>{current_part.upper()}</strong></div>'
                
            user_ans = q.get("user_answer", "Chưa chọn")
            correct_ans = q.get("correct_answer", "")
            
            choices_layout_html = ""
            status_line_html = ""
            
            student_choice = user_ans.strip().upper()
            if "CHỌN: " in student_choice:
                student_choice = student_choice.split("CHỌN: ")[-1].strip()
            if "CHƯA CHỌN" in student_choice or "A)" in student_choice:
                student_choice = ""

            clean_correct = correct_ans.strip().upper()
            if "ĐÁP ÁN ĐÚNG:" in clean_correct:
                clean_correct = clean_correct.split("ĐÁP ÁN ĐÚNG:")[-1].strip()
            if not clean_correct:
                clean_correct = "A"

            # 1. TRÍCH XUẤT VÀ SỬ DỤNG TRỌN VẸN HTML CÔNG THỨC ĐÃ DỊCH TỪ FRONTEND
            labels = ["A", "B", "C", "D"]
            keys_map = ["opt_A", "opt_B", "opt_C", "opt_D"]
            opts_clean = []

            for o_idx, lbl in enumerate(labels):
                raw_opt_text = q.get(keys_map[o_idx])
                if raw_opt_text is None:
                    opt_text = f"Phương án {lbl}"
                else:
                    opt_text = str(raw_opt_text).strip()
                opts_clean.append(opt_text)

            # --- TRƯỜNG HỢP 1: CÂU TRẮC NGHIỆM ĐƠN PHẦN I ---
            if "Phần I" in current_part or clean_correct in ["A", "B", "C", "D"]:
                choices_layout_html += '<table class="web-options-grid"><tr>'
                for o_idx, lbl in enumerate(labels):
                    if o_idx == 2:
                        choices_layout_html += '</tr><tr>'
                        
                    is_selected = (student_choice == lbl)
                    dot_class = "radio-dot checked" if is_selected else "radio-dot"
                    
                    choices_layout_html += f"""
                    <td>
                        <span class="{dot_class}"></span>
                        <span class="opt-label-text"><strong>{lbl}.</strong> {opts_clean[o_idx]}</span>
                    </td>
                    """
                choices_layout_html += '</tr></table>'
                
                is_correct = (student_choice == clean_correct) or "✔ ĐÚNG" in user_ans.upper()
                if is_correct:
                    status_line_html = f'<div class="status-web-line correct-web">✔ Đúng (Đáp án chính xác: {clean_correct})</div>'
                else:
                    status_line_html = f'<div class="status-web-line wrong-web">❌ Chưa chính xác (Đáp án đúng: {clean_correct})</div>'
            
            # --- TRƯỜNG HỢP 2: CÂU TRẮC NGHIỆM ĐÚNG/SAI PHẦN II ---
            elif "Phần II" in current_part or " | " in user_ans:
                p2_data = q.get("p2_data", {}) or {}
                user_ans_html = ""
                for k, v in p2_data.items():
                    u_part = v.get("user", "Chưa chọn")
                    c_part = v.get("correct", "")
                    color_u = "#137333" if u_part == c_part else "#c5221f"
                    user_ans_html += f'<span class="badge-opt"><strong>{k})</strong> Bạn: <span style="color:{color_u}; font-weight:bold;">{u_part}</span> | Bộ: <strong>{c_part}</strong></span>'

                choices_layout_html = f'<div class="opts-flex-container">{user_ans_html}</div>'
                
                if "✔" in user_ans or user_ans == correct_ans:
                    status_line_html = '<div class="status-web-line correct-web">✔ Đúng toàn bộ các ý lựa chọn</div>'
                else:
                    status_line_html = '<div class="status-web-line wrong-web">❌ Có ý lựa chọn chưa chính xác</div>'
            
            # --- TRƯỜNG HỢP 3: CÂU ĐIỀN NGẮN PHẦN III ---
            else:
                is_correct = user_ans.strip() == correct_ans.strip()
                choices_layout_html = f'<div style="margin: 8px 0; font-size:14px;"><strong>Kết quả điền:</strong> {user_ans}</div>'
                if is_correct:
                    status_line_html = f'<div class="status-web-line correct-web">✔ Đúng (Đáp án: {correct_ans})</div>'
                else:
                    status_line_html = f'<div class="status-web-line wrong-web">❌ Chưa chính xác (Đáp án đúng: {correct_ans})</div>'

            # Đổ trực tiếp mã HTML câu hỏi thu được từ Frontend (Giữ nguyên vẹn 100% công thức)
            questions_html += f"""
            <div class="question-card">
                <div class="question-text">
                    <strong>Câu {index}:</strong> {q.get("question_text", "")}
                </div>
                {choices_layout_html}
                {status_line_html}
                {f'<div class="explanation-card"><strong>💡 Hướng dẫn giải chi tiết:</strong><br>{q.get("explanation", "")}</div>' if q.get("explanation") else ''}
            </div>
            """
#============================================================================
        pdf_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script type="text/javascript" async
                src="https://cloudflare.com">
            </script>
            <style>
                /* CĂN LỀ CHUẨN ĐỀ THI BỘ GIÁO DỤC: 12mm giúp trang giấy gọn gàng, cân đối */
                @page {{ size: A4; margin: 12mm 12mm 15mm 12mm; }}
                body {{ font-family: "Times New Roman", Times, serif; color: #000000; line-height: 1.4; font-size: 14px; }}
                
                /* Tiêu đề đầu trang và khung mã đề thi chính quy */
                .mo-header {{ width: 100%; border-collapse: collapse; margin-bottom: 5px; }}
                .mo-header td {{ vertical-align: top; font-size: 13px; }}
                .text-upper {{ text-transform: uppercase; font-weight: bold; }}
                .line-under {{ text-decoration: underline; padding-bottom: 2px; }}
                .student-info-bar {{ width: 100%; border-collapse: collapse; margin: 10px 0; border-top: 1px solid #000; border-bottom: 1px solid #000; padding: 4px 0; }}
                .code-box {{ border: 2px solid #000; padding: 3px 12px; font-weight: bold; font-size: 14px; float: right; letter-spacing: 1px; background: #fff; }}
                
                /* Tiêu đề Phần gạch chân đậm bo sát theo phong cách đề thi gốc */
                .part-header-box {{ border: 1.5px solid #000; padding: 6px 10px; font-size: 13.5px; font-weight: bold; text-align: left; margin: 20px 0 12px 0; background-color: #fcfcfc; page-break-after: avoid; text-transform: uppercase; }}
                
                /* Khối câu hỏi trắc nghiệm A4 chống cắt dòng */
                .question-card {{ margin-bottom: 18px; page-break-inside: avoid; }}
                .question-text {{ font-size: 14.5px; text-align: justify; margin-bottom: 8px; font-weight: normal; }}
                
                /* MA TRẬN GRID ĐÁP ÁN: Ép 2 cột đối xứng tuyệt đối phẳng hàng */
                .web-options-grid {{ width: 100%; border-collapse: collapse; margin: 6px 0; }}
                .web-options-grid td {{ width: 50%; padding: 4px 2px; vertical-align: middle; font-size: 14.5px; text-align: justify; }}
                
                /* Vẽ ô tròn trắc nghiệm chuẩn chỉ */
                .radio-dot {{
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border: 1.5px solid #000000;
                    border-radius: 50%;
                    vertical-align: middle;
                    margin-right: 6px;
                    background-color: #ffffff;
                }}
                .radio-dot.checked {{
                    background-color: #000000;
                    box-shadow: inset 0 0 0 2px #ffffff;
                }}
                .opt-label-text {{ vertical-align: middle; }}
                
                /* Thanh thông báo kết quả và Giải chi tiết */
                .status-web-line {{ margin: 6px 0; padding: 5px 10px; font-weight: bold; font-size: 13px; border-radius: 3px; }}
                .correct-web {{ color: #137333; background-color: #e6f4ea; border-left: 4px solid #137333; }}
                .wrong-web {{ color: #c5221f; background-color: #fce8e6; border-left: 4px solid #c5221f; }}
                .explanation-card {{ margin-top: 8px; padding: 10px 12px; background-color: #fffdf3; border-left: 4px solid #f2994a; border-radius: 0 4px 4px 0; font-size: 13.5px; border-right: 1px solid #f0e4b2; border-top: 1px solid #f0e4b2; border-bottom: 1px solid #f0e4b2; text-align: justify; }}
                /* --- KHẮC PHỤC TRIỆT ĐỂ LỖI VỠ CÔNG THỨC PHÂN SỐ DỌC GÂY TRÀN TRANG --- */
                .frac {{ 
                    display: inline-table; 
                    vertical-align: middle; 
                    text-align: center; 
                    padding: 0 3px; 
                    line-height: 1.1; 
                }}
                .frac .num {{ 
                    display: table-row; 
                    border-bottom: 1px solid #000000; 
                    padding-bottom: 1px; 
                    font-style: italic; 
                }}
                .frac .den {{ 
                    display: table-row; 
                    padding-top: 1px; 
                    font-style: italic; 
                }}          
                /* ──────── THƯ VIỆN LÕI CSS DỰNG CÔNG THỨC TỰ CHẾ CHO PDF ──────── */
                .frac {{ 
                    display: inline-table; 
                    vertical-align: middle; 
                    text-align: center; 
                    padding: 0 3px; 
                    line-height: 1.1; 
                }}
                .frac .num {{ 
                    display: table-row; 
                    border-bottom: 1px solid #000000; 
                    padding-bottom: 1px; 
                    font-style: italic; 
                }}
                .frac .den {{ 
                    display: table-row; 
                    padding-top: 1px; 
                    font-style: italic; 
                }}                
                .integral-container {{ 
                    display: inline-table; 
                    vertical-align: middle; 
                    line-height: 1; 
                    padding: 0 2px; 
                }}
                .integral-symbol {{ 
                    font-size: 22px; 
                    font-family: "Times New Roman", serif; 
                    display: table-cell; 
                    vertical-align: middle; 
                }}
                .integral-limits {{ 
                    display: inline-block; 
                    vertical-align: middle; 
                    font-size: 9px; 
                    line-height: 1.0; 
                    margin-left: -2px; 
                }}
                .integral-upper {{ display: block; }}
                .integral-lower {{ display: block; }}       
                /* ──────── THƯ VIỆN CSS NÂNG CẤP VÀ LỜI GIẢI ──────── */
                .hat, .angle-hat {{
                    position: relative;
                    display: inline-block;
                    padding-top: 2px;
                }}
                .hat::before, .angle-hat::before {{
                    content: "^";
                    position: absolute;
                    top: -5px;
                    left: 50%;
                    transform: translateX(-50%) scaleX(1.3);
                    font-size: 11px;
                    font-weight: bold;
                }}
                /* Định dạng hộp giải chi tiết, chống tràn mép */
                .explanation-card {{ 
                    margin-top: 10px; 
                    padding: 12px; 
                    background-color: #fffdf3; 
                    border-left: 4px solid #f2994a; 
                    border-radius: 0 4px 4px 0; 
                    border: 1px solid #f0e4b2;
                    border-left-width: 4px;
                    text-align: justify;
                    page-break-inside: avoid;
                }}                         
            </style>
        </head>
        <body>
            <table class="mo-header">
                <tr>
                    <td width="45%" align="center">
                        <span class="text-upper">BỘ GIÁO DỤC VÀ ĐÀO TẠO</span><br>
                        <span class="text-upper line-under">ĐỀ THI CHÍNH THỨC</span>
                    </td>
                    <td width="55%" align="center">
                        <span class="text-upper" style="font-size: 14px;">KỲ THI TỐT NGHIỆP TRUNG HỌC PHỔ THÔNG NĂM 2026</span><br>
                        <strong>Môn thi: VẬT LÝ</strong><br>
                        <span style="font-style: italic;">Thời gian làm bài: 50 phút, không kể thời gian phát đề</span>
                    </td>
                </tr>
            </table>

            <div style="width: 100%; overflow: hidden; margin-top: 10px;">
                <div class="code-box">Mã đề: 0214</div>
                <div style="font-size: 14px; padding-top: 5px;">
                    <strong>Họ, tên thí sinh:</strong> {data.name}<br>
                    <strong>Tổng điểm đạt được:</strong> <span style="color:#d93025; font-weight:bold; font-size:16px;">{r.get("total_score", 0)} / 10 điểm</span>
                </div>
            </div>

            <table class="student-info-bar">
                <tr>
                    <td style="font-size: 12px; color: #555;">Thống kê tổng hợp số câu đúng chi tiết: Phần I: {r.get("score_p1", 0)} câu | Phần II: {r.get("score_p2", 0)} câu | Phần III: {r.get("score_p3", 0)} câu</td>
                </tr>
            </table>

            {questions_html}
        </body>
        </html>
        """

        options = {'encoding': "UTF-8", 'javascript-delay': '2500', 'no-outline': None}
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: pdfkit.from_string(pdf_html, pdf_filename, options=options))

        msg = MIMEMultipart('mixed')
        msg['From'] = f"VietDragon <{SENDER_EMAIL}>"
        msg['To'] = data.email
        msg['Subject'] = Header(f"KẾT QUẢ THI - {data.name}", 'utf-8').encode()
        msg.attach(MIMEText("Chào bạn, VietDragon gửi bạn phiếu kết quả thi thử nghiệm.", 'plain', 'utf-8'))
        
        with open(pdf_filename, "rb") as f:
            part = MIMEBase("application", "pdf")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        safe_filename = unicodedata.normalize('NFKD', pdf_filename).encode('ascii', 'ignore').decode('utf-8')
        part.add_header("Content-Disposition", f'attachment; filename="{safe_filename}"')
        msg.attach(part)

        await asyncio.wait_for(aiosmtplib.send(msg, hostname=SMTP_SERVER, port=SMTP_PORT, username=SENDER_EMAIL, password=SENDER_PASSWORD, start_tls=True), timeout=15.0)
        return {"success": True, "message": "Đã tạo file PDF chuẩn Bộ GD và gửi Mail thành công!"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if os.path.exists(pdf_filename):
            os.remove(pdf_filename)
# --End---- ĐỒNG BỘ DỮ LIỆU VÀ XỬ LÝ GỬI EMAIL MÔN VẬT LÝ ----------------

