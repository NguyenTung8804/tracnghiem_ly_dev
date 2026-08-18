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
                    
            # ──────── LỌC SẠCH BÁCH RÁC CHỮ NHÂN ĐÔI THEO PHONG CÁCH CŨ ────────
                    current_opt_text = str(opts_clean[o_idx])
                    import re
                    current_opt_text = re.sub(r'<[^>]*>', '', current_opt_text)
            # Quét sạch bất kỳ chữ cái nào (A-D) đứng độc lập kèm dấu chấm bám ngay sau dấu tròn
                    current_opt_text = re.sub(r'[○●]\s*[A-Za-z]\.\s*', '', current_opt_text)
                    current_opt_text = re.sub(r'^[A-Za-z]\.\s*', '', current_opt_text)
                    current_opt_text = re.sub(r'[○●]', '', current_opt_text).strip()

                    choices_layout_html += f"""
                    <td>
                        <span class="{dot_class}"></span>
                        <span class="opt-label-text">{current_opt_text}</span>
                    </td>
                    """
                choices_layout_html += '</tr></table>'
                
                is_correct = (student_choice == clean_correct) or "✔ ĐÚNG" in user_ans.upper()
                if is_correct:
                    status_line_html = f'<div class="status-web-line correct-web">✔ Đúng (Đáp án chính xác: {clean_correct})</div>'
                else:
                    status_line_html = f'<div class="status-web-line wrong-web">❌ Chưa chính xác (Đáp án đúng: {clean_correct})</div>'
            
            # --- TRƯỜNG HỢP 2: CÂU TRẮC NGHIỆM ĐÚNG/SAI PHẦN II ---
#===============================================================
            elif p2_data and len(p2_data) >= 4:
                # Bắt trúng đích Câu hỏi Đúng/Sai Phần II dựa vào độ dài dữ liệu chấm điểm
                # CHIẾN THUẬT ĐỘT PHÁ: Bóc tách nội dung chữ các ý từ trường Hướng dẫn giải chi tiết
                explain_text = str(q.get("huong_dan_giai", "") or q.get("explain", ""))
                parts_p2 = {'a': '', 'b': '', 'c': '', 'd': ''}
                
                try:
                    if 'a)' in explain_text:
                        rem_a = explain_text.split('a)', 1)[1]
                        parts_p2['a'] = rem_a.split('b)', 1)[0].strip() if 'b)' in rem_a else rem_a.strip()
                    if 'b)' in explain_text:
                        rem_b = explain_text.split('b)', 1)[1]
                        parts_p2['b'] = rem_b.split('c)', 1)[0].strip() if 'c)' in rem_b else rem_b.strip()
                    if 'c)' in explain_text:
                        rem_c = explain_text.split('c)', 1)[1]
                        parts_p2['c'] = rem_c.split('d)', 1)[0].strip() if 'd)' in rem_c else rem_c.strip()
                    if 'd)' in explain_text:
                        parts_p2['d'] = explain_text.split('d)', 1)[1].strip()
                except Exception:
                    pass
                
                # Dựng hộp bảng điểm Phần II ma trận phẳng vuông vắn tăm tắp tuyệt đẹp
                user_ans_html = '<div style="margin-top:8px!important; font-weight:bold!important; color:#1a73e8!important; font-size:14px!important;">PHẦN II: Câu hỏi trắc nghiệm Đúng/Sai</div>'
                user_ans_html += '<table style="width:100%!important;border-collapse:collapse!important;margin-top:6px!important;font-size:13px!important;border:1px solid #dee2e6!important;">'
                user_ans_html += '<thead>'
                user_ans_html += '<tr style="background-color:#f8f9fa!important;border-bottom:2px solid #dee2e6!important;text-align:center!important;font-weight:bold!important;">'
                user_ans_html += '<th style="padding:6px!important;width:40px!important;border:1px solid #dee2e6!important;">Ý</th>'
                user_ans_html += '<th style="padding:6px!important;text-align:left!important;border:1px solid #dee2e6!important;">Nội dung phát biểu phương án trắc nghiệm</th>'
                user_ans_html += '<th style="padding:6px!important;width:75px!important;border:1px solid #dee2e6!important;">Bạn chọn</th>'
                user_ans_html += '<th style="padding:6px!important;width:75px!important;border:1px solid #dee2e6!important;">Đáp án</th>'
                user_ans_html += '<th style="padding:6px!important;width:110px!important;border:1px solid #dee2e6!important;background-color:#fff3cd!important;">Đánh giá</th>'
                user_ans_html += '</tr>'
                user_ans_html += '</thead>'
                user_ans_html += '<tbody>'
                
                # Duyệt qua 4 nhãn chữ cái để đổ dữ liệu vào từng hàng của bảng
                for lbl_idx, lbl in enumerate(['a', 'b', 'c', 'd']):
                    raw_v = p2_data.get(lbl, {}) if isinstance(p2_data, dict) else {}
                    if not raw_v and isinstance(p2_data, dict):
                        raw_v = p2_data.get("Đáp án " + lbl.upper(), {})
                    
                    u_part = str(raw_v.get("user", "Chưa chọn"))
                    c_part = str(raw_v.get("correct", ""))
                    
                    # Lấy nội dung chữ phẳng đã bóc tách được từ trường giải chi tiết
                    opt_text_p2 = parts_p2.get(lbl, "")
                    
                    # Làm sạch các từ chỉ thị thừa ở đầu câu giải chi tiết (như "Sai vì", "Đúng vì") để trả lại phát biểu trơn
                    for prefix in ["Sai vì ", "Đúng vì ", "Sai do ", "Đúng do ", "Sai ", "Đúng "]:
                        if opt_text_p2.startswith(prefix):
                            opt_text_p2 = opt_text_p2[len(prefix):].strip()
                    # Viết hoa lại chữ cái đầu tiên của câu cho ngay ngắn chỉn chu
                    if opt_text_p2:
                        opt_text_p2 = opt_text_p2[0].upper() + opt_text_p2[1:]
                    else:
                        opt_text_p2 = "Phát biểu ý " + lbl.upper() + " của câu hỏi tương ứng."
                    
                    if u_part == "Chưa chọn" or not u_part:
                        status_text = '<span style="color:#666!important;">Chưa chọn</span>'
                        color_u = "#666"
                    elif u_part.lower() == c_part.lower():
                        status_text = '<span style="color:#137333!important;font-weight:bold!important;">✓ Đúng</span>'
                        color_u = "#137333"
                    else:
                        status_text = '<span style="color:#c5221f!important;font-weight:bold!important;">✗ Sai</span>'
                        color_u = "#c5221f"
                    
                    user_ans_html += '<tr style="border-bottom:1px solid #dee2e6!important;text-align:center!important;">'
                    user_ans_html += '<td style="padding:8px!important;font-weight:bold!important;border:1px solid #dee2e6!important;background-color:#f8f9fa!important;">' + lbl.lower() + ')</td>'
                    user_ans_html += '<td style="padding:8px!important;text-align:left!important;border:1px solid #dee2e6!important;">' + opt_text_p2 + '</td>'
                    user_ans_html += '<td style="padding:8px!important;font-weight:bold!important;color:' + color_u + '!important;border:1px solid #dee2e6!important;">' + u_part + '</td>'
                    user_ans_html += '<td style="padding:8px!important;font-weight:bold!important;color:#137333!important;border:1px solid #dee2e6!important;">' + c_part + '</td>'
                    user_ans_html += '<td style="padding:8px!important;border:1px solid #dee2e6!important;background-color:#fffdf4!important;">' + status_text + '</td>'
                    user_ans_html += '</tr>'
                    
                user_ans_html += "</tbody></table>"
                choices_layout_html = '<div style="width:100%!important;margin-bottom:10px!important;">' + user_ans_html + '</div>'
#=========================================================                
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
            # ──────── BỘ DỊCH CÔNG THỨC TOÁN PHẲNG ADAPTER CHO THÂN CÂU HỎI ────────
            def backend_math_interpreter(text_str):
                if not text_str:
                    return ""
                s = str(text_str)
                
                # BỘ LỌC THÔNG MINH ĐÓN ĐẦU: Dịch ngay khi chuỗi dữ liệu Database còn nguyên vẹn gạch chéo
                # # BỘ LỌC THÔNG MINH ĐÓN ĐẦU: Dịch chuẩn xác theo 1 dấu gạch chéo gốc của Database
                            # ──────── ĐẶC TRỊ MŨ GÓC MA TRẬN BẢNG PHẲNG ĐỒNG BỘ CHO PDF ────────
            # Thuật toán quét tất cả dải mã mang hình dáng dấu mũ trong bảng mã Unicode (\^, ˆ, ∧, ̂) đứng trước chữ cái
                import re
                s = re.sub(r'[\^ˆ∧̂]\s*ABC',\
                    
                  r'<table style="display: inline-table !important; vertical-align: middle !important; border-collapse: collapse !important; text-align: center !important; line-height: 0.5 !important; margin: 0 1px !important;"><tr><td style="padding: 0 !important; text-align: center !important; font-size: 0.85em !important; font-weight: bold !important; height: 4px !important; line-height: 4px !important;">^</td></tr><tr><td style="padding: 0 !important; text-align: center !important; line-height: 1.1 !important;"><strong>ABC</strong></td></tr></table>', s)
            
                s = re.sub(r'[\^ˆ∧̂]\s*(α|\\alpha|alpha)',\
                     
               r'<table style="display: inline-table !important; vertical-align: middle !important; border-collapse: collapse !important; text-align: center !important; line-height: 0.5 !important; margin: 0 1px !important;"><tr><td style="padding: 0 !important; text-align: center !important; font-size: 0.85em !important; font-weight: bold !important; height: 4px !important; line-height: 4px !important;">^</td></tr><tr><td style="padding: 0 !important; text-align: center !important; line-height: 1.1 !important;"><strong>α</strong></td></tr></table>', s)
                       
                s = re.sub(r'\\widehat\{([^}]+)\}',\
                
                r'<table style="display: inline-table !important; vertical-align: middle !important; border-collapse: collapse !important; text-align: center !important; line-height: 0.5 !important; margin: 0 1px !important;"><tr><td style="padding: 0 !important; text-align: center !important; font-size: 0.85em !important; font-weight: bold !important; height: 4px !important; line-height: 4px !important;">^</td></tr><tr><td style="padding: 0 !important; text-align: center !important; line-height: 1.1 !important;"><strong>\1</strong></td></tr></table>', s)
    
                # 1. CHUẨN HÓA KÝ TỰ HỆ THỐNG: ÉP dọn sạch các dấu gạch chéo ngược thoát chuỗi từ database
                s = s.replace("\\\\frac{", "\\frac{").replace("\\\\\\\\frac{", "\\frac{")
                s = s.replace("\\\\sqrt{", "\\sqrt{").replace("\\\\\\\\sqrt{", "\\sqrt{")
                s = s.replace("\\\\widehat{", "\\widehat{").replace("\\\\int", "\\int")
                
                # 2. BỘ LỌC CUỐN CHIẾU TỪ TRONG RA NGOÀI (Học tập 100% từ cấu trúc dòng 810 của index.html)
                loop_counter = 0
                while loop_counter < 60:
                    last_frac = s.rfind(r'\frac{')
                    last_sqrt = s.rfind(r'\sqrt{')
                    
                    if last_frac == -1 and last_sqrt == -1:
                        break
                        
                    # Trường hợp 1: Phân số \frac{ nằm sâu ở lõi trong cùng thì dịch trước
                    if last_frac != -1 and (last_frac > last_sqrt or last_sqrt == -1):
                        num_start = last_frac + 6
                        open_braces = 1
                        i = num_start
                        while open_braces > 0 and i < len(s):
                            if s[i] == '{': open_braces += 1
                            elif s[i] == '}': open_braces -= 1
                            i += 1
                        num_content = s[num_start : i-1]
                        
                        if i < len(s) and s[i] == '{':
                            den_start = i + 1
                            open_braces = 1
                            i += 1
                            while open_braces > 0 and i < len(s):
                                if s[i] == '{': open_braces += 1
                                elif s[i] == '}': open_braces -= 1
                                i += 1
                            den_content = s[den_start : i-1]
                            full_frac = s[last_frac : i]
                            
                            # Dựng cấu trúc bảng phân số dọc .frac đồng dạng 100% với phần đáp án của bạn
                            frac_html = f'<table class="frac"><tr><td class="num">{num_content}</td></tr><tr><td class="den">{den_content}</td></tr></table>'
                            s = s.replace(full_frac, frac_html)
                        else:
                            break
                            
                    # Trường hợp 2: Căn thức \sqrt{ nằm sâu ở lõi trong cùng thì dịch trước
                    elif last_sqrt != -1:
                        start = last_sqrt + 6
                        open_braces = 1
                        i = start
                        while open_braces > 0 and i < len(s):
                            if s[i] == '{': open_braces += 1
                            elif s[i] == '}': open_braces -= 1
                            i += 1
                        inner_content = s[start : i-1]
                        full_sqrt = s[last_sqrt : i]
                        
                        # Dựng cấu trúc khối hộp căn thức tự chế phẳng có gạch viền ngang đỉnh đầu
                        sqrt_html = f'<span class="sqrt-container"><span class="sqrt-symbol">√</span><span class="sqrt-content">{inner_content}</span></span>'
                        s = s.replace(full_sqrt, sqrt_html)
                        
                    loop_counter += 1

                # 3. Dịch các ký hiệu tích phân phẳng, mũ góc và chữ cái Vật lý còn lại
                import re
                s = re.sub(r'\\int_\{?([^}^]+)\}?\^\{?([^}{\s<>]+)\}?', r'∫<sub>\1</sub><sup>\2</sup>', s)
                s = s.replace(r"\int", "∫").replace("\\int", "∫")
                s = s.replace(r"\textbf{", "<strong>").replace(r"}", "</strong>").replace("\\", "")
                return s
            # ──────── BỘ LỌC ĐỒNG BỘ PHÂN TÁCH NỘI DUNG PHẦN II TRÊN PDF ────────
            # Học tập chính xác cách bóc tách chuỗi bằng dấu cắt 'a)' của giao diện Web
            clean_q_text = str(q.get("question_text", ""))
            if "Phần II" in current_part or "cac_lua_chon" not in q or " Đúng" in str(q.get("user_answer")):
                if "<strong>a)</strong>" in clean_q_text: clean_q_text = clean_q_text.split("<strong>a)</strong>")[0]
                elif "<b>a)</b>" in clean_q_text: clean_q_text = clean_q_text.split("<b>a)</b>")[0]
                elif "a)" in clean_q_text: clean_q_text = clean_q_text.split("a)")[0]
                clean_q_text = clean_q_text.strip()
            
            # Tiến hành ép chuỗi thân câu hỏi độc lập và lời giải qua bộ dịch đệ quy cuốn chiếu giống đáp án
            clean_q_text = backend_math_interpreter(clean_q_text)
            clean_expl = backend_math_interpreter(q.get("explanation", ""))

            # Đổ chuỗi HTML an toàn bằng hàm .format() và bảo vệ các ngoặc nhọn, lồng lời giải chi tiết cộng chuỗi sạch cú pháp Python
            questions_html += """
            <div class="question-card">
                <div class="question-text">
                    <strong>Câu {idx}:</strong> {q_text}
                </div>
                {layout}
                {status}
                {expl_card}
            </div>
            """.format(
                idx=index,
                q_text=clean_q_text,
                layout=choices_layout_html,
                status=status_line_html,
                expl_card='<div class="explanation-card"><strong>💡 Hướng dẫn giải chi tiết:</strong><br>' + str(clean_expl) + '</div>' if q.get("explanation") else ''
            )
#============================================================================
            # ──────── ĐẶC TRỊ GÓC MŨ PHẲNG TUYỆT ĐỐI TRƯỚC KHI IN PDF ────────
            # Thay thế trực diện chuỗi thô bốc từ Frontend truyền lên để phá vỡ lỗi lệch lề

            # ──────── ĐẶC TRỊ GÓC MŨ PHẲNG TUYỆT ĐỐI TRƯỚC KHI IN PDF ────────
            # Thay thế trực diện trên cả Thân câu hỏi (clean_q_text) và Đáp án (choices_layout_html)
            for target in ['^ABC', '^ABC']:
                clean_q_text = clean_q_text.replace(target, '<table style="display: inline-table; vertical-align: middle; border-collapse: collapse; text-align: center; line-height: 0.5; margin: 0 1px;"><tr><td style="padding: 0; text-align: center; font-size: 0.85em; font-weight: bold; height: 4px; line-height: 4px;">^</td></tr><tr><td style="padding: 0; text-align: center; line-height: 1.1;"><strong>ABC</strong></td></tr></table>')
                choices_layout_html = choices_layout_html.replace(target, '<table style="display: inline-table; vertical-align: middle; border-collapse: collapse; text-align: center; line-height: 0.5; margin: 0 1px;"><tr><td style="padding: 0; text-align: center; font-size: 0.85em; font-weight: bold; height: 4px; line-height: 4px;">^</td></tr><tr><td style="padding: 0; text-align: center; line-height: 1.1;"><strong>ABC</strong></td></tr></table>')
            
            for target in ['^α', '^ α', '^α', '^ α']:
                clean_q_text = clean_q_text.replace(target, '<table style="display: inline-table; vertical-align: middle; border-collapse: collapse; text-align: center; line-height: 0.5; margin: 0 1px;"><tr><td style="padding: 0; text-align: center; font-size: 0.85em; font-weight: bold; height: 4px; line-height: 4px;">^</td></tr><tr><td style="padding: 0; text-align: center; line-height: 1.1;"><strong>α</strong></td></tr></table>')
                choices_layout_html = choices_layout_html.replace(target, '<table style="display: inline-table; vertical-align: middle; border-collapse: collapse; text-align: center; line-height: 0.5; margin: 0 1px;"><tr><td style="padding: 0; text-align: center; font-size: 0.85em; font-weight: bold; height: 4px; line-height: 4px;">^</td></tr><tr><td style="padding: 0; text-align: center; line-height: 1.1;"><strong>α</strong></td></tr></table>') 
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
                /* ─── THƯ VIỆN CĂN THỨC TỰ CHẾ ĐỒNG BỘ 100% TỪ FRONTEND ─── */
                .sqrt-container {{
                    display: inline-flex;
                    align-items: flex-start;
                    vertical-align: middle;
                    position: relative;
                    line-height: 1;
                }}
                .sqrt-symbol {{
                    font-family: "Times New Roman", serif;
                    font-size: 1.1em;
                    user-select: none;
                }}
                .sqrt-content {{
                    border-top: 1.5px solid #000000;
                    padding-top: 1px;
                    padding-left: 1px;
                    margin-left: -1px;
                    display: inline-block;
                }}                       
                /* ══════════════════════════════════════════════════════════ */
                /* ── THƯ VIỆN LÕI CSS ĐẶC TRỊ CĂN LỒNG PHÂN SỐ ĐỒNG BỘ 100% ── */
                /* ══════════════════════════════════════════════════════════ */      
                /* Thiết lập phom dáng bảng phẳng (inline-table) để triệt tiêu lỗi hiển thị */
                .frac, .sqrt-container {{
                    display: inline-table !important;
                    vertical-align: middle !important;
                    border-collapse: collapse !important;
                    line-height: 1.1 !important;
                }}
                .frac td, .sqrt-content {{
                    padding: 0 !important;
                    text-align: center !important;
                    font-style: italic !important;
                }}
                /* Định nghĩa lại nét gạch phân số và dấu căn rõ nét */
                .frac .num {{ border-bottom: 1.2px solid #000 !important; padding-bottom: 2px !important; }}
                .frac .den {{ padding-top: 2px !important; }}
                .sqrt-symbol {{ font-size: 1.15em !important; padding-right: 1px !important; }}
                .sqrt-content {{ border-top: 1.3px solid #000 !important; padding-top: 1px !important; }}
                /* ── BỘ ĐỊNH VỊ HÌNH HỌC THÔNG MINH ÉP DẤU MŨ LÊN ĐỈNH ĐẦU CHỮ ── */
                .hat, [class*="hat"] {{
                    display: inline-block !important;
                    position: relative !important;
                    padding-top: 0.3em !important;
                    line-height: 1 !important;
                    vertical-align: bottom !important;
                }}
                .hat sup, [class*="hat"] sup {{
                    position: absolute !important;
                    top: -0.3em !important;
                    left: 50% !important;
                    transform: translateX(-50%) scaleX(1.5) !important;
                    font-size: 0.9em !important;
                    font-weight: bold !important;
                }}
                /* Phòng vệ từ xa: Nếu dấu mũ là ký tự trơn ^ đứng trước chữ cái */
                span.hat, td .hat, .angle-hat {{
                    position: relative !important;
                }}                
                /* ── THƯ VIỆN MA TRẬN BẢNG KHÓA TÂM MŨ GÓC ĐỒNG BỘ ĐÁP ÁN ── */
                .hat-table {{
                    display: inline-table !important;
                    vertical-align: middle !important;
                    border-collapse: collapse !important;
                    text-align: center !important;
                    line-height: 0.8 !important;
                    margin: 0 2px !important;
                }}
                .hat-table td {{
                    padding: 0 !important;
                    text-align: center !important;
                }}
                .hat-sym {{
                    font-size: 0.9em !important;
                    font-weight: bold !important;
                    height: 8px !important;
                    line-height: 8px !important;
                }}
                .hat-txt {{
                    line-height: 1.1 !important;
                }}
                /* ── THƯ VIỆN MA TRẬN BẢNG KHÓA TÂM MŨ GÓC ĐỒNG BỘ ĐÁP ÁN ── */
                .hat-table {{
                    display: inline-table !important;
                    vertical-align: middle !important;
                    border-collapse: collapse !important;
                    text-align: center !important;
                    line-height: 0.8 !important;
                    margin: 0 2px !important;
                }}
                .hat-table td {{
                    padding: 0 !important;
                    text-align: center !important;
                }}
                .hat-sym {{
                    font-size: 0.9em !important;
                    font-weight: bold !important;
                    height: 8px !important;
                    line-height: 8px !important;
                }}
                .hat-txt {{
                    line-height: 1.1 !important;
                }}                
                /* ── THƯ VIỆN MA TRẬN BẢNG KHÓA TÂM MŨ GÓC ĐỒNG BỘ FILE PDF ── */
                .hat-table {{
                    display: inline-table !important;
                    vertical-align: middle !important;
                    border-collapse: collapse !important;
                    text-align: center !important;
                    line-height: 0.7 !important;
                    margin: 0 1px !important;
                }}
                .hat-table td {{
                    padding: 0 !important;
                    text-align: center !important;
                }}
                .hat-sym {{
                    font-size: 0.85em !important;
                    font-weight: bold !important;
                    height: 6px !important;
                    line-height: 6px !important;
                }}
                .hat-txt {{
                    line-height: 1.1 !important;
                }}                
                /* ── THƯ VIỆN ĐẶC TRỊ MŨ GÓC ĐỘC LẬP HOÀN TOÀN KHÔNG DÙNG REGEX ── */
                .hat, [class*="hat"], .angle-container {{
                    display: inline-block !important;
                    position: relative !important;
                    line-height: 1 !important;
                    padding-top: 0.25em !important;
                }}
                /* Ép dấu mũ lơ lửng của hệ thống nhảy vào đúng vị trí trung tâm đỉnh đầu */
                .hat sup, .angle-hat, [class*="hat"] sup {{
                    position: absolute !important;
                    top: -0.25em !important;
                    left: 50% !important;
                    transform: translateX(-50%) scaleX(1.4) !important;
                    font-size: 0.85em !important;
                    font-weight: bold !important;
                    visibility: visible !important;
                }}
                /* ĐẬP TAN DẤU MŨ THÔ LỆCH LỀ: Ép ẩn biến mất hoàn toàn dấu mũ thô bướng bỉnh đứng trước */
                span:contains("^"), span:contains("ˆ"), td:contains("^") {{
                    text-indent: 0 !important;
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

