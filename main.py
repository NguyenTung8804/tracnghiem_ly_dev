import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict

app = FastAPI()

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

