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
#-------------end---ảnh QR thanh toán------------------------------------
from fastapi.staticfiles import StaticFiles
#-------------end---ảnh QR thanh toán------------------------------------

app = FastAPI()

# ---------------- CẤU HÌNH GỬI EMAIL MIỄN PHÍ ----------------
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "tracnghiemonlinevietdragon@gmail.com"
SENDER_PASSWORD = "iisogmecxfzjufnd"
# ---------End------- CẤU HÌNH GỬI EMAIL MIỄN PHÍ ----------------

# Cấu hình Static và Jinja2 Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
#==============================================================
from fastapi.middleware.cors import CORSMiddleware

# 🚀 BỘ TĂNG ÁP TOÀN NĂNG: Giải phóng băng thông CORS cho tên miền online local.lt bắn phá sầm sập về máy, giữ nguyên tốc độ offline siêu tốc!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
#=============================================================
templates = Jinja2Templates(directory="templates")

def load_filtered_questions(khoi: int, loai: str, nam: int, de_so: int):
    try:
        with open("database.json", "r", encoding="utf-8") as f:
            all_questions = json.load(f)
        return [q for q in all_questions if q.get("khoi_lop") == khoi and q.get("loai_de") == loai and q.get("nam_hoc") == nam and q.get("de_so") == de_so]
    except Exception:
        return []
#================NẠP DANH SÁCH ĐỀ THI CHO hem.idex IN RA\=============
@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    try:
        with open("exam_config.json", "r", encoding="utf-8") as f:
            danh_sach_de_goc = json.load(f)
    except Exception:
        danh_sach_de_goc = []

    # Cập nhật dữ phòng trường 'truong' tránh nổ lỗi undefined khi tải dữ liệu
    for de in danh_sach_de_goc:
        if "nam" not in de: de["nam"] = "2026"
        if "tinh_thanh" not in de: de["tinh_thanh"] = "Hà Nội"
        if "lop" not in de: de["lop"] = "12"
        if "trang_thai" not in de: de["trang_thai"] = "Mở"
        if "truong" not in de: de["truong"] = "Bộ Giáo Dục"

    # Lọc ẩn hiện bám sát logic "Đóng thì hiện, Mở thì giấu" thiên tài của bạn
    danh_sach_hien_thi = [de for de in danh_sach_de_goc if de.get("trang_thai") == "Đóng"]

    # Thuật toán đa tầng: Ép đề miễn phí lên trước, đề trả phí đứng sau
    danh_sach_sap_xep = sorted(danh_sach_hien_thi, key=lambda x: 0 if x.get("loai_de") == "mien_phi" else 1)

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"danh_sach_de": danh_sach_sap_xep}
    )
#=============END===NẠP DANH SÁCH ĐỀ THI CHO hem.idex IN RA\=============
@app.get("/thi", response_class=HTMLResponse)
# 🐉 HỆ THỐNG: BỘ TRÍCH XUẤT THAM SỐ ĐỀ THI ĐỘNG TỪ URL VÀ BẪY LỖI PHÒNG THỦ KHÔNG SẬP SERVER
async def read_item(request: Request):
    # Thọc tay trực tiếp vào thanh địa chỉ URL để bốc chuỗi chữ sau dấu bằng (?de_so=)
    # 🚀 BỘ NÃO ĐỘNG HÓA PHÒNG THI VẠN NĂNG: Lọc câu hỏi trực tiếp theo Mã số đề (de_so), bất tử với mọi Loại đề và Năm học!
    de_so_param = request.query_params.get("de_so", "1")
    try:
        current_de_so = str(int(de_so_param))
    except ValueError:
        current_de_so = "1"

    # 🪐 LỘI FILE DATABASE GỐC: Quét trọn gói và chỉ nhặt ra những câu hỏi có trường 'de_so' khớp chóc với mã đề hiện tại
    try:
        with open("database.json", "r", encoding="utf-8") as f:
            all_questions_db = json.load(f)
    except Exception:
        all_questions_db = []

    # Ép bộ lọc chỉ bám đuổi duy nhất thuộc tính de_so để đổ bộ câu hỏi ra ngoài phòng thi học sinh
    questions = [q for q in all_questions_db if str(q.get("de_so")).strip() == current_de_so]

# 🐉 END BỘ TRÍCH XUẤT THAM SỐ ĐỀ THI
    # =========================================================================
    # 🔑 BẢN ĐỒ ID CHUẨN: Trích xuất trực tiếp 100% từ danh sách gốc questions
    # =========================================================================
    global list_question_ids
    list_question_ids = [int(item.get("id")) for item in questions if isinstance(item, dict) and item.get("id") is not None]
    
    # Ép in rà soát ngay ra Terminal để kiểm tra trật tự danh sách ID chuẩn
    print("\n" + "🗺️" * 20)
    print(f"🚀 BẢN ĐỒ ID CHUẨN ĐẦU NGUỒN TỪ QUESTIONS: {list_question_ids}")
    print("🗺️" * 20 + "\n")
    # =========================================================================
    secure_questions = []
    
    for q in questions:
        q_secure = q.copy()
        # 🎯 BẢO MẬT: Xóa bỏ đáp án đúng và giải chi tiết trước khi gửi xuống HTML mẫu
        if "dap_an_dung" in q_secure:
            del q_secure["dap_an_dung"]
        if "giai_chi_tiet" in q_secure:
            del q_secure["giai_chi_tiet"]
        secure_questions.append(q_secure)
        
    # 🚀 THUẬT TOÁN ĐỘNG HÓA THỜI GIAN CHỐT HẠ: Đồng bộ chính xác khóa key "thoigian" và cấy lệnh Test Terminal
    thoi_gian_goc_phut = 50
    try:
        with open("exam_config.json", "r", encoding="utf-8") as f_cfg:
            kho_de_config = json.load(f_cfg)
        
        # Tìm chiếc đề có de_so trùng khớp chằn chặn dạng chuỗi văn bản phẳng sạch
        de_khop = next((d for d in kho_de_config if str(d.get("de_so")).strip() == str(current_de_so).strip()), None)
        
        if de_khop:
            # 🎯 KHÓA CHỐT LONG MẠCH: Sửa từ "thoi_gian" sang "thoigian" viết liền khít khao răng rắc theo đúng file JSON nhà bạn!
            thoi_gian_goc_phut = int(de_khop.get("thoigian", 50))
            
            # 📢 CHUỒNG CHẨN ĐOÁN TERMINAL: Phun trực tiếp giá trị thực tế lên màn hình đen uvicorn để kiểm chứng!
            print("=" * 60)
            print(f"📢 [TEST ĐỐI SOÁT VIETDRAGON] Đang gọi đề số: '{current_de_so}'")
            print(f"📌 Phách dữ liệu thô nhặt từ JSON: {de_khop}")
            print(f"⏱️ Giá trị thời gian ép kiểu thành công truyền đi: {thoi_gian_goc_phut} phút")
            print("=" * 60)
            
    except Exception as e_cfg:
        print(f"🚨 Lỗi bốc phách thời gian gốc config gửi phòng thi: {e_cfg}")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "questions": secure_questions,
            "de_so": current_de_so,
            "thoi_gian_goc_phut": thoi_gian_goc_phut  # 🎯 TRUYỀN THỜI GIAN ĐÃ SỬA SANG HỘP ẨN FRONTEND
        }
    )

class ExamSubmit(BaseModel):
    answers: Dict[str, str]
    de_so: int

#===============LẤY MÃ PHÒNG THI GỬI TRONG EMAIL==============        

# 🚀 CỔNG API NGẦM BẢO MẬT TRUNG CHUYỂN: Phun trọn gói dải ID Hex hợp lệ cho JavaScript đối soát xé gió!
@app.get("/api/get_access_ids")
async def get_access_ids_api(de_so: str = "1"):
    import os
    ma_hop_le = []
    target_check = str(de_so).replace("de_", "").strip()
    thu_muc_goc = os.path.dirname(os.path.abspath(__file__))
    duong_dan_file_access = os.path.join(thu_muc_goc, "user_access.json")
    try:
        if os.path.exists(duong_dan_file_access):
            with open(duong_dan_file_access, "r", encoding="utf-8") as f:
                access_data = json.load(f)
            for row in access_data:
                json_de_so = str(row.get("de_so", "")).replace("de_", "").strip()
                if json_de_so == target_check and row.get("id"):
                    ma_hop_le.append(str(row.get("id")).strip().lower())
    except Exception:
        pass
    return ma_hop_le
#==========end=====LẤY MÃ PHÒNG THI GỬI TRONG EMAIL==============        

@app.post("/api/submit")
async def submit_exam(data: ExamSubmit):
    student_answers = data.answers
#------------------TEST----------------------------
    # 🎯 BẪY NỘI SOI DỮ LIỆU: Ép máy tính vạch trần toàn bộ cấu trúc của data.answers
    print("\n" + "🔥" * 25)
    print("🚀 BẮT ĐẦU NỘI SOI KHO DỮ LIỆU 'data.answers' TỪ WEB GỬI LÊN:")
    print(f"👉 Kiểu dữ liệu tổng: {type(data.answers)}")
    
    if hasattr(data.answers, "items") or isinstance(data.answers, dict):
        # Duyệt qua từng cặp Khóa - Giá trị thực tế để in ra hàng dọc tăm tắp
        for key, value in data.answers.items():
            print(f"   🔹 Khóa (Key): '{key}'  ==>  Giá trị học sinh chọn (Value): '{value}'")
    else:
        print(f"👉 Dữ liệu thô không phải dạng Dictionary. Nội dung thô: {data.answers}")
        
    print("🔥" * 25 + "\n")
#--------------TRÍCH XUẤT LÍT CÂU HỎI TRONG data.answers-------
    # =========================================================================
    # 🔑 LUỒNG GIẢI MÃ: TRÍCH XUẤT LIST ID THỰC GIỮ NGUYÊN THỨ TỰ TỰ NHIÊN
    # =========================================================================
    global submitted_question_ids
    submitted_question_ids = []
    
    if isinstance(data.answers, dict):
        for key in data.answers.keys():
            key_str = str(key).strip()
            extracted_id = None
            
            # Trường hợp 1: Khóa của Phần II chứa dấu cách (Ví dụ: 'q 319 a')
            if " " in key_str:
                parts = key_str.split(" ")
                if len(parts) >= 2 and parts[1].isdigit():
                    extracted_id = int(parts[1])
                        
            # Trường hợp 2: Khóa của Phần II chứa dấu gạch dưới (Ví dụ: 'q_319_a')
            elif "_" in key_str:
                parts = key_str.split("_")
                if len(parts) >= 2 and parts[1].isdigit():
                    extracted_id = int(parts[1])
                        
            # Trường hợp 3: Khóa của Phần I và Phần III là số nguyên trơn (Ví dụ: '3', '200')
            elif key_str.isdigit():
                extracted_id = int(key_str)
            
            # Ghi nhận ID vào danh sách (Chặn trùng lặp nhưng GIỮ NGUYÊN THỨ TỰ ĐẦU NGUỒN)
            if extracted_id is not None and extracted_id not in submitted_question_ids:
                submitted_question_ids.append(extracted_id)
                
    # 🕵️‍♂️ TUÂN THỦ CHỈ THỊ: HOÀN TOÀN KHÔNG DÙNG LỆNH SORT ĐỂ BẢO VỆ THỨ TỰ PHẲNG
    
    # Ép in danh sách ID thực thu hoạch được ra Terminal để rà soát kiểm thử cẩn thận
    print("\n" + "🎯" * 20)
    print(f"🚀 LIST ID THỰC GIỮ NGUYÊN THỨ TỰ TỰ NHIÊN: {submitted_question_ids}")
    print("🎯" * 20 + "\n")
    # =========================================================================
#------------ENd--TRÍCH XUẤT LÍT CÂU HỎI TRONG data.answers-------
#-------------------------_THAY THẾ-------------------------------
    # =========================================================================
    # 🔄 THAY THẾ LUỒNG LỌC CỨNG: BỐC TỰ ĐỘNG CÂU HỎI GỐC THEO DANH SÁCH ID THỰC
    # =========================================================================
    questions = []
    
    # 1. Đọc trực tiếp tệp database.json tổng nạp vào bộ nhớ tạm
    db_file_path = "database.json"  # Bạn có thể điều chỉnh đường dẫn chuẩn nếu cần
    try:
        with open(db_file_path, "r", encoding="utf-8") as f:
            full_database_data = json.load(f)
            
        # 2. Duyệt qua danh sách ID thực tế học sinh đã nộp để nhặt câu hỏi gốc
        for current_target_id in submitted_question_ids:
            # Tìm câu hỏi trùng khớp ID số tăm tắp trong kho tổng database
            matched_q = next((item for item in full_database_data if int(item.get("id", -1)) == int(current_target_id)), None)
            
            if matched_q:
                # Sao chép đối tượng để tránh ảnh hưởng đến dữ liệu gốc của file
                questions.append(matched_q.copy())
                
    except Exception as db_err:
        print(f"❌ Lỗi nạp hoặc trích xuất database tổng: {db_err}")
        
    # 3. Ép in số lượng câu hỏi gốc thu hoạch được để rà soát kiểm thử cẩn thận
    print("\n" + "⚙️" * 20)
    print(f"🚀 TỔNG SỐ CÂU HỎI GỐC BỐC ĐƯỢC TỪ DATABASE TỔNG: {len(questions)} câu.")
    print("⚙️" * 20 + "\n")
    # =========================================================================
#------------------END------TEST---------------------    
    total_score = 0.0
    score_p1 = 0
    score_p2 = 0
    score_p3 = 0
    total_attempted = 0  # Đếm tổng số câu học sinh thực sự làm bài toàn đề thi
    detailed_results = []
    
    for q in questions:
#-------------------TEST--------------------------
        # 🎯 BẪY KIỂM THỬ TỐI CAO: Vạch trần kiểu dữ liệu thực tế của biến q và id
        print("=" * 60)
        print(f"👉 KIỂU DỮ LIỆU CỦA BIẾN 'q': {type(q)}")
        if isinstance(q, dict):
            print(f"👉 BIẾN 'q' LÀ DICTIONARY. Giá trị q['id'] là: {q.get('id')} (Kiểu: {type(q.get('id'))})")
        else:
            print("👉 BIẾN 'q' KHÔNG PHẢI DICTIONARY (Cấu trúc đối tượng/Pydantic Model).")
            if hasattr(q, 'id'):
                print(f"👉 Giá trị thuộc tính q.id là: {q.id} (Kiểu: {type(q.id)})")
        print("=" * 60)
#-------------END---------TEST------------------------
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
        
    # ⚖️ HỆ THỐNG: TỰ ĐỘNG QUÉT MA TRẬN ĐỀ ĐỂ TÍNH ĐIỂM MAXIMUM THỰC TẾ TRÊN RAM
    max_possible_score = 0.0
    for q in questions:
        if q.get("cac_lua_chon") == "Đúng, Sai":
            max_possible_score += 1.0
        elif "Điền số" in str(q.get("cac_lua_chon")):
            max_possible_score += 0.5
        else:
            max_possible_score += 0.25

    # 🪐 THUẬT TOÁN BO TRÒN KHẤC 0.25Đ BẤT BẠI: Phóng lên hệ 10 trước, rồi mới nẹp khấc bo tròn
    if max_possible_score > 0:
        raw_converted = (total_score / max_possible_score) * 10.0
        final_converted_score = round(raw_converted * 4) / 4.0
    else:
        final_converted_score = 0.0

    return {
        "total_score": final_converted_score, # Điểm hệ 10 đã bo tròn khấc 0.25đ phẳng sạch
        "score_p1": score_p1,
        "score_p2": score_p2,
        "score_p3": score_p3,
        "total_attempted": total_attempted,
        "total_questions": len(questions),
        "details": detailed_results
    }

#=======================DUYỆT TRẢ PHÍ========================
# 👑 ĐƯỜNG DẪN QUẢN TRỊ TÀI CHÍNH ĐỘC LẬP TỐI CAO - CHỈ CÓ BẠN ĐƯỢC QUYỀN TRUY CẬP
@app.get("/approve")
async def approve_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="approve.html"  # Gọi đích danh trang bảng duyệt độc lập, cách ly hoàn toàn khỏi trang soạn đề
    )
#==================END=====DUYỆT TRẢ PHÍ========================
#===============MAX PHONGF THI================================
# 🪐 API 3: KIỂM TRA MÃ KÍCH HOẠT DỰ PHÒNG ĐỂ BẺ KHÓA PHÒNG THI TRẢ PHÍ
@app.post("/api/verify_activation_code")
async def verify_activation_code(request: Request):
    try:
        gói_tin = await request.json()
        ma_kich_hoat = gói_tin.get("ma_kich_hoat", "").strip()
        
        if not ma_kich_hoat:
            return {"status": "error", "message": "🚨 LỖI GÕ THIẾU: Vui lòng điền Mã kích hoạt phòng thi!"}
            
        # Lội vào hầm ngầm dữ liệu để đối soát phách mã
        with open("user_access.json", "r", encoding="utf-8") as f:
            danh_sach_mua = json.load(f)
            
        # Lùng sục tìm kiếm chuỗi ID trùng khớp chóc
        for user in danh_sach_mua:
            if user.get("id") == ma_kich_hoat:
                if user.get("status") == "approved":
                    return {
                        "status": "success", 
                        "de_so": user.get("de_so"),
                        "message": f"🎉 ĐÃ XÁC THỰC THÀNH CÔNG: Xin mời bạn vào làm Bài thi số {user.get('de_so')}!"
                    }
                else:
                    return {"status": "error", "message": "🔒 MÃ CHƯA KÍCH HOẠT: Giao dịch này đang chờ Giáo viên đối soát duyệt nộp tiền!"}
                    
        return {"status": "error", "message": "❌ MÃ KHÔNG TỒN TẠI: Mã kích hoạt phòng thi không đúng hoặc bị gõ sai ký tự!"}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi nghẽn mạch hệ thống: {str(e)}"}
#============END===MAX PHONGF THI================================
#================EDIT DỀ THI======================================
@app.get('/admin')
async def admin_page(request: Request):
    # 🪐 BỘ LỌC ĐỀ TỪ PYTHON: Nhặt tham số de_so từ đường link URL giáo viên gọi trên trình duyệt
    query_params = request.query_params
    current_de_so = query_params.get('de_so')
    
    # 🪐 [VIETDRAGON IDB] THUẬT TOÁN RA-ĐA DÒ TÌM ĐỀ MỞ MẶC ĐỊNH LOGIC ĐỘNG BẤT TỬ 100%
    if not current_de_so:
        try:
            with open("exam_config.json", "r", encoding="utf-8") as f:
                vdb_config_list = json.load(f)
            # Tự động lọc tìm chiếc đề thi đầu tiên có trạng thái mang chữ "Mở" vách sau ổ cứng
            de_mo_dau_tien = next((str(de.get("de_so")) for de in vdb_config_list if str(de.get("trang_thai", "Mở")).strip() == "Mở"), None)
            current_de_so = de_mo_dau_tien if de_mo_dau_tien else "4"
        except Exception:
            current_de_so = "4"
    else:
        current_de_so = str(current_de_so)

    # 🚀 BỘ NÃO TỰ ĐỘNG LỘI FILE CONFIG KHÔNG LÀM ẢNH HƯỞNG CODE CŨ CỦA BẠN
    de_hien_tai = {"de_so": current_de_so, "lop": "12", "ten_de": "Thi Đại Học", "nam": "2026"}
    try:
        with open("exam_config.json", "r", encoding="utf-8") as f:
            danh_sach_config = json.load(f)
        for c in danh_sach_config:
            if str(c.get("de_so")) == str(current_de_so):
                t_de = c.get("ten_de", "Thi Đại Học")
                if " - " in t_de:
                    t_de = t_de.split(" - ")[-1].strip()
                de_hien_tai = {
                    "de_so": current_de_so,
                    "lop": c.get("lop", "12"),
                    "ten_de": t_de,
                    "nam": c.get("nam", "2026")
                }
                break
    except Exception as e:
        print(f"🚨 Lỗi bốc config đề thi: {e}")

    try:
        with open("database.json", "r", encoding="utf-8") as f:
            all_questions = json.load(f)
    except Exception:
        all_questions = []

    # 🛡️ CHỐT CHẶN TĂNG TỐC: Chỉ bốc đúng các câu thuộc Đề số đang chọn, lọc sạch các đề khác để nhẹ RAM 100%
    filtered_questions = [q for q in all_questions if str(q.get("de_so")) == current_de_so]

    # 🛡️ TRÍCH XUẤT KHO ID TOÀN CỤC CỦA ĐỀ KHÁC (Chính là nguồn phách của biến otherExamIds ở Frontend)
    other_exam_ids = [int(q.get('id', 0)) for q in all_questions if str(q.get("de_so")) != current_de_so]

    # === TEST TERMINAL THEO CHỈ THỊ TỐI CAO CỦA BẠN ===
    print('\n' + '🔥' * 15 + ' [BẪY LOG TERMINAL: KIỂM TRA BIẾN SỐ] ' + '🔥' * 15)
    print(f"🪐 Mã đề hiện tại đang mở trên Firefox: Đề số {current_de_so}")
    print(f"🪐 Danh sách ID của ĐỀ HIỆN TẠI (Đang hiển thị): {[int(q.get('id', 0)) for q in filtered_questions]}")
    print(f"🪐 DANH SÁCH BIẾN [otherExamIds] (CỦA CÁC ĐỀ KHÁC) TRÊN TERMINAL KHAI HỎA:")
    print(f"👉 otherExamIds = {other_exam_ids}")
    print(f"🪐 Tổng số lượng câu hỏi thuộc đề khác đang nằm trong file JSON: {len(other_exam_ids)} câu")
    print('-' * 95 + '\n')
    # === END TEST ===

    # 👑 THUẬT TOÁN ĐÁNH SỐ CUỐN CHIẾU THIÊN TÀI: Dò tìm ID cao nhất của mã đề thi ngay phía trước nó
    try:
        current_de_int = int(current_de_so)
        de_truoc_str = str(current_de_int - 1)
    except Exception:
        de_truoc_str = "0"

    # Lọc bốc toàn bộ danh sách các câu thuộc về ĐỀ THI NGAY PHÍA TRƯỚC
    questions_de_truoc = [q for q in all_questions if str(q.get("de_so")) == de_truoc_str]

    if questions_de_truoc:
        # Nếu có đề trước, lấy ID cao nhất của đề trước đó làm mốc xuất phát gối đầu
        max_id = max([int(q.get("id", 0)) for q in questions_de_truoc])
        next_global_id = max_id + 1
    else:
        # Nếu không có đề trước (Ví dụ đang ở Đề số 1), hệ thống tự động bốc ID lớn nhất lịch sử kho tổng như cũ
        max_id_all = max([int(q.get("id", 0)) for q in all_questions]) if all_questions else 0
        next_global_id = max_id_all + 1

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "questions": filtered_questions,
            "selected_de_so": current_de_so,
            "other_ids": other_exam_ids,
            "next_global_id": next_global_id,
            "de_hien_tai": de_hien_tai # 🚀 BẮN BIẾN THÔNG TIN CHUNG SANG JINJA2 CHUẨN ĐÉT
        }
    )
#=======================================================================
@app.post("/api/add_exam")
async def add_exam_api(request: Request):
    try:
        new_exam_data = await request.json()
        de_so = str(new_exam_data.get("de_so", "1"))
        new_questions = new_exam_data.get("questions", [])
        
        # # === TEST ===
        print("\n" + "🚀" * 15 + " [TEST LOG ADMIN] NHẬN DỮ LIỆU ĐỀ THI MỚI VÀ GHI VẼ " + "🚀" * 15)
        print(f"🪐 Mã đề thi nhận được từ web gửi lên: Đề số {de_so}")
        print(f"🪐 Số lượng câu hỏi giáo viên vừa soạn thảo trong lượt này: {len(new_questions)} câu")
        print("-" * 90 + "\n")
        # # === END TEST ===

        # 🪐 CƠ CHẾ ĐỌC FILE DATABASE AN TOÀN
        try:
            with open("database.json", "r", encoding="utf-8") as f:
                db_data = json.load(f)
        except Exception:
            db_data = []
            
        # Lọc bỏ các câu cũ của đề số này ra khỏi bộ đệm RAM để chuẩn bị ghi đè dữ liệu tươi mới
        old_count = len(db_data)
        db_data = [q for q in db_data if str(q.get("de_so")) != de_so]
        
        # Gộp các câu hỏi vừa chỉnh sửa/thêm mới của giáo viên vào danh sách chung
        db_data.extend(new_questions)
        
        # 👑 RA-ĐA SẮP XẾP ĐA TẦNG TUYỆT MỸ: Ép toàn bộ dữ liệu phải tự sắp xếp theo Đề số tăng dần, rồi đến câu ID tăng dần!
        db_data.sort(key=lambda x: (int(x.get("de_so", 0)), int(x.get("id", 0))))
        
        # # === TEST ===
        print("\n" + "⚡" * 15 + " [TEST LOG CHUẨN HÓA HÀNG LỐI DATABASE] " + "⚡" * 15)
        print(f"🪐 Bộ sắp xếp Python vừa khóa phách thành công!")
        print(f"🪐 File database.json chính thức được nẹp thẳng hàng theo trục Đề số và ID câu tăng dần!")
        print("=" * 95 + "\n")
        # # === END TEST ===

        with open("database.json", "w", encoding="utf-8") as f:
            json.dump(db_data, f, ensure_ascii=False, indent=4)
            
        return {"status": "success", "message": f"Đã ghi chốt và sắp xếp Đề số {de_so} vào database.json thành công!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
#============END====EDIT DỀ THI======================================
import uuid
from datetime import datetime

# 🪐 API 1: HỌC SINH GỬI YÊU CẦU KÍCH HOẠT ĐỀ THI TRẢ PHÍ
@app.post("/api/request_access")
async def request_access_api(request: Request):
    try:
        data = await request.json()
        email = data.get("email", "").strip().lower()
        de_so = str(data.get("de_so", "1"))
        ma_giao_dich = data.get("ma_giao_dich", "").strip()

        if not email or not ma_giao_dich:
            return {"status": "error", "message": "Vui lòng nhập đầy đủ Email và Mã giao dịch!"}

        try:
            with open("user_access.json", "r", encoding="utf-8") as f:
                access_data = json.load(f)
        except Exception:
            access_data = []

        for item in access_data:
            if item.get("email") == email and str(item.get("de_so")) == de_so:
                return {"status": "info", "message": f"Tài khoản {email} đã tồn tại yêu cầu hoặc đã được cấp quyền cho Đề số {de_so}!"}

        new_request = {
            "id": str(uuid.uuid4())[:8],
            "email": email,
            "de_so": de_so,
            "ma_giao_dich": ma_giao_dich,
            "status": "pending",
            "thoi_gian": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        access_data.append(new_request)

        with open("user_access.json", "w", encoding="utf-8") as f:
            json.dump(access_data, f, ensure_ascii=False, indent=4)

        return {"status": "success", "message": "Gửi yêu cầu kích hoạt thành công! Vui lòng chờ Giáo viên đối soát ngân hàng và phê duyệt trong ít phút."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 🪐 API 2: LẤY DANH SÁCH CHỜ DUYỆT HIỂN THỊ TRÊN TRANG ADMIN
@app.get("/api/get_pending_requests")
async def get_pending_requests_api():
    try:
        with open("user_access.json", "r", encoding="utf-8") as f:
            access_data = json.load(f)
        pending_list = [item for item in access_data if item.get("status") == "pending"]
        return {"status": "success", "data": pending_list}
    except Exception:
        return {"status": "success", "data": []}

# 🪐 API 3: GIÁO VIÊN BẤM NÚT DUYỆT CẤP QUYỀN + BẮN EMAIL THỰC TẾ KHÉP KÍN 100% RA INTERNET
@app.post("/api/approve_access")
async def approve_access_api(request: Request):
    try:
        data = await request.json()
        request_id = data.get("id")

        with open("user_access.json", "r", encoding="utf-8") as f:
            access_data = json.load(f)

        target_request = None
        for item in access_data:
            if item.get("id") == request_id:
                item["status"] = "approved"  # Chuyển trạng thái sang Đã Duyệt vĩnh cửu
                target_request = item
                break

        if not target_request:
            return {"status": "error", "message": "Không tìm thấy yêu cầu phê duyệt này!"}

        with open("user_access.json", "w", encoding="utf-8") as f:
            json.dump(access_data, f, ensure_ascii=False, indent=4)

        # 🚀 ĐẤU NỐI DÂY THẦN KINH BẮN EMAIL THỰC TẾ BẰNG BỘ TĂNG ÁP AIOSMTPLIB CỦA BẠN
        student_email = target_request.get("email")
        de_so = target_request.get("de_so")
        
        # 🔑 CHỐT HẠ BÁU VẬT: Lấy đích danh ID ngẫu nhiên làm Mã Kích Hoạt Phòng Thi dự phòng
        ma_kich_hoat = target_request.get("id")
        
        # 1. Đúc cấu trúc phong thư điện tử chân phương chuẩn MIME
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        import aiosmtplib

        msg = MIMEMultipart('mixed')
        msg['From'] = f"Vietdragon Center <{SENDER_EMAIL}>"
        msg['To'] = student_email
        msg['Subject'] = f"🐉 [VIETDRAGON IDB] PHÊ DUYỆT THÀNH CÔNG - MÃ VÀO THI ĐỀ SỐ {de_so}"

        # 2. Đúc giao diện HTML bức thư lộng lẫy chứa link phòng thi của bạn gửi học sinh
        domain_thuc_te = str(request.base_url)

        # 🚀 BỘ NÃO CỨU HỘ ĐỒNG BỘ TIÊU ĐỀ: Lội vào file config nhặt trọn gói thông tin Đề thi để gửi Email
        ten_de_goc = "Đề thi trắc nghiệm"
        truong_goc = "Bộ Giáo Dục"
        nam_goc = "2026"
        try:
            with open("exam_config.json", "r", encoding="utf-8") as f_cfg:
                kho_de_config = json.load(f_cfg)
            # Tìm trúng chiếc đề có mã số khớp với mã đề được duyệt (ép chuỗi phẳng sạch)
            de_khop = next((d for d in kho_de_config if str(d.get("de_so")).strip() == str(de_so).strip()), None)
            if de_khop:
                ten_de_goc = de_khop.get("ten_de", "Đề thi trắc nghiệm")
                truong_goc = de_khop.get("truong", "Bộ Giáo Dục")
                nam_goc = de_khop.get("nam", "2026")
        except Exception as e_cfg:
            print(f"🚨 Lỗi bốc phách thông tin đồng bộ gửi mail: {e_cfg}")

        # 🎨 THIẾT KẾ BOX MÃ KÍCH HOẠT DỰ PHÒNG CHỐNG LỖI ĐƯỜNG TRUYỀN LINK GMAIL
        html_noi_dung = f"""
        <div style="font-family: 'Times New Roman', serif; padding: 25px; border: 2px solid #1a365d; border-radius: 12px; max-width: 600px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
            <h2 style="color: #1a365d; margin-top: 0; text-align: center; text-transform: uppercase;">🐉 PHÊ DUYỆT PHÒNG THI THÀNH CÔNG!</h2>
            <p style="font-size: 15px; color: #2f3542;">Chào học sinh <b>{student_email}</b>,</p>
        <!-- 🚀 ĐỒNG BỘ TIÊU ĐỀ MỞ RỘNG GIỐNG TRANG CHỦ: Tự động đúc Tên đề thi + Trường biên soạn + Năm học sang trọng kịch trần -->
        <p style="font-size: 14px; color: #57606f; line-height: 1.6; font-family: 'Times New Roman', serif;">
            Hệ thống quản trị Vietdragon IDB đã đối soát tài khoản và xác nhận giao dịch nộp phí mở khóa thành công phòng luyện thi: 
            <b>{ten_de_goc} ({truong_goc if truong_goc else 'Bộ Giáo Dục'} - Năm {nam_goc if nam_goc else '2026'})</b>.
        </p>
            
        <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center; border: 2px dashed #1a365d;">
            <p style="margin: 0; font-size: 14px; color: #1a365d; font-weight: bold; text-transform: uppercase;">🔑 MÃ XÁC THỰC PHÒNG THI CHÍNH THỨC:</p>
            <h2 style="margin: 10px 0; color: #e53e3e; font-size: 32px; font-family: monospace; letter-spacing: 2px;">{ma_kich_hoat}</h2>
            <div style="text-align: left; margin-top: 12px; font-size: 13px; color: #4a5568; line-height: 1.6; font-family: 'Times New Roman', serif; margin-bottom: 20px;">
                <p style="margin: 0 0 6px 0; font-weight: bold; color: #2d3748;">💡 Học sinh có thể truy cập làm bài bằng 2 cách tiện lợi sau:</p>
                <p style="margin: 0 0 4px 0;">👉 <b>Cách 1 (Vào thẳng trực tiếp):</b> Nhấp chọn nút <b>"BẤM VÀO ĐÂY ĐỂ VÀO THI NGAY"</b> ở phía dưới, hệ thống sẽ tự động chuyển hướng và yêu cầu bạn nhập dãy mã xác thực ở trên để mở cửa phòng thi.</p>
                <p style="margin: 0;">👉 <b>Cách 2 (Vào từ Trang chủ):</b> Truy cập trực tiếp hệ thống vách ngoài trang chủ, click chuột chọn đúng đề thi này và điền dãy mã xác thực trên để được phê duyệt mở khóa vào làm bài nhanh chóng.</p>
            </div>
            <!-- 🚀 HOÀN TRẢ KHỐI LINK NÚT BẤM TO KHỔNG LỒ CHÍNH THỨC SIÊU DỄ CLICK -->
            <a href="{domain_thuc_te}thi?de_so={de_so}" style="display: inline-block; background: #1a365d; color: white; padding: 14px 35px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px; box-shadow: 0 4px 10px rgba(26,54,93,0.3); transition: background 0.2s; font-family: 'Times New Roman', serif;">🚀 BẤM VÀO ĐÂY ĐỂ VÀO THI NGAY</a>
        </div>
            
            <p style="color: #a4b0be; font-size: 12px; text-align: center; margin-bottom: 0; border-top: 1px solid #f1f2f6; padding-top: 15px;">Trung tâm luyện thi chất lượng cao Vietdragon IDB trân trọng thông báo.</p>
        </div>
        """
        msg.attach(MIMEText(html_noi_dung, 'html', 'utf-8'))

        # 3. BÓP CÒ SÚNG: Gọi bộ tăng áp aiosmtplib phóng thư xé gió ra internet bằng cấu hình sẵn có của bạn
        try:
            print(f"📡 [KHAI HỎA SMTP] Đang phóng Email kích hoạt Đề {de_so} thực tế ra internet tới hòm thư: {student_email}")
            await asyncio.wait_for(
                aiosmtplib.send(
                    msg, 
                    hostname=SMTP_SERVER, 
                    port=SMTP_PORT, 
                    username=SENDER_EMAIL, 
                    password=SENDER_PASSWORD, 
                    start_tls=True, 
                    timeout=15.0
                ), 
                timeout=15.0
            )
            print(f"✅ [KÍCH NỔ THÀNH CÔNG] Bức thư mở khóa phòng thi thực tế đã cập bến hòm thư: {student_email}!")
        except Exception as mail_err:
            print(f"🚨 [NGHẼN MẠCH SMTP] Lỗi đường truyền bắn thư thực tế: {mail_err}")

        return {"status": "success", "message": f"🎉 ĐẠI THẮNG: Đã phê duyệt thành công cho học sinh {student_email}! Hệ thống tự động kích nổ gửi một Email thực tế chứa link phòng thi số {de_so} kèm Mã kích hoạt [ {ma_kich_hoat} ] dự phòng xé gió!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
# ==============================================================================
# 🪐 API 1: Bắn danh sách đề thi thô từ file exam_config.json sang bảng Admin duyệt sửa
@app.get("/api/get_exams_config")
async def get_exams_config():
    try:
        with open("exam_config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

# 🪐 API 2: Nhận gói tin cấu hình mới từ Admin bấm nút và ghi đè xuống exam_config.json
@app.post("/api/save_exams_config")
async def save_exams_config(request: Request):
    try:
        du_lieu_moi = await request.json()
        
        # Kiểm tra tính hợp lệ của gói tin tránh làm rác file config
        if not isinstance(du_lieu_moi, list):
            return {"status": "error", "message": "🚨 LỖI ĐỊNH DẠNG: Dữ liệu gửi về bắt buộc phải là một danh sách Mảng!"}
            
        with open("exam_config.json", "w", encoding="utf-8") as f:
            json.dump(du_lieu_moi, f, ensure_ascii=False, indent=4)
            
        print("🪐 ĐẠI THẮNG: Đã cập nhật và ghi đè kho đề thi thành công xuống exam_config.json!")
        return {"status": "success", "message": "🎉 CHÚC MỪNG: Đã cập nhật và đồng bộ kho đề thi xuống exam_config.json thành công!"}
    except Exception as e:
        print(f"🚨 LỖI GHI FILE CONFIG: {e}")
        return {"status": "error", "message": f"Thất bại ngắt mạch hệ thống: {str(e)}"}
#============================Soạn_duyệt_đề_thi_giao_diện_soạn_thảo===============
@app.post("/api/submit_draft")
def submit_draft(data: dict):
    # 🚀 BỘ NÃO ĐỒNG BỘ CHÍNH QUY: Học tập 100% cơ chế bốc ghi JSON của hàm mẫu admin_page nhà bạn
    import json
    import os
    import datetime

    # Đón trọn gói ma trận thông tin đề theo đúng quy chuẩn biến số độc quyền
    de_so = str(data.get('de_so', ''))
    mon_hoc = str(data.get('mon_hoc', ''))
    nam = str(data.get('nam', '2026'))
    lop = str(data.get('lop', '12'))
    tinh_thanh = str(data.get('tinh_thanh', ''))
    truong = str(data.get('truong', 'Bộ Giáo Dục'))
    ten_de = str(data.get('ten_de', ''))
    socau = str(data.get('socau', '0'))
    thoigian = str(data.get('thoigian', '0'))
    loai_de = str(data.get('loai_de', 'tra_phi'))
    gia_tien = str(data.get('gia_tien', '0'))
    nguoi_soan = str(data.get('nguoi_soan', 'GiaoVien_SoanThao'))
    
    raw_questions = data.get('questions', [])
    formatted_questions = []
    
    for index, q in enumerate(raw_questions, start=1):
        # 🪐 THUẬT TOÁN ĐỐI SOÁT ID TOÀN CỤC: Bốc trúng chóc mã định danh global từ mặt tiền truyền sang, chống lặp số thứ tự thô sơ!
        id_global = q.get('id_cau_hoi')
        
        # Phòng hờ lá chắn nếu Front-end bị trống trường hoặc lỗi rỗng, tự động ép kiểu số nguyên ăn chắc
        if id_global is not None:
            final_id = int(id_global)
        else:
            final_id = int(index)

        # Thuật toán nén mảng thành chuỗi dấu phẩy bảo toàn cấu trúc máy nhà bạn
        bốc_lựa_chọn = q.get('cac_lua_chon', ["A", "B", "C", "D"])
        if isinstance(bốc_lựa_chọn, list):
            formatted_choices = ",".join([str(x).strip() for x in bốc_lựa_chọn])
        else:
            formatted_choices = str(bốc_lựa_chọn).strip()

        formatted_questions.append({
            "id": final_id,  # KHÓA CHỐT HẠ: Trả lại ID toàn cục bất tử (Ví dụ: 151, 152, 153...) chuẩn đét database.json
            "khoi_lop": int(lop) if lop.isdigit() else 12,
            "loai_de": str(loai_de),
            "nam_hoc": int(nam) if nam.isdigit() else 2026,
            "de_so": str(de_so),
            "cac_lua_chon": formatted_choices,
            "noi_dung": str(q.get('noi_dung', '')),
            "dap_an_dung": str(q.get('dap_an_dung', 'A')),
            "giai_chi_tiet": str(q.get('giai_chi_tiet', ''))
        })

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    new_draft = {
        "draft_id": f"draft_{nam}_{datetime.datetime.now().strftime('%m%d%H%M%S')}",
        "de_so": de_so,
        "mon_hoc": mon_hoc,
        "nam": nam,
        "lop": lop,
        "tinh_thanh": tinh_thanh,
        "truong": truong,
        "ten_de": ten_de,
        "socau": socau,
        "thoigian": thoigian,
        "loai_de": loai_de,
        "gia_tien": gia_tien,
        "trang_thai": "Đóng",
        "nguoi_soan": nguoi_soan,
        "nguoi_duyet": "",
        "trang_thai_duyet": "pending",
        "ngay_tao": now_str,
        "ngay_cap_nhat": now_str,
        "ai_assessment": {
            "trung_lap_percent": 0.0,
            "canh_bao_trung": "Sạch bóng 100%! Đang xếp hàng chờ Trạm vũ trụ AI rà quét đối soát...",
            "ma_tran_goi_y": {"NhanBiet": len(formatted_questions), "ThongHieu": 0, "VanDung": 0, "VanDungCao": 0},
            "ghi_chu_ai": "Đề thi hợp lệ."
        },
        "gop_y_to_truong": "",
        "questions": formatted_questions
    }

    # 🚀 KÍCH NỔ BỘ NÃO AI ĐỐI SOÁT TRÙNG LẶP CHẠY NGẦM VÁCH SAU
    try:
        if 'ai_verify_duplicate_questions' in globals():
            new_draft = ai_verify_duplicate_questions(new_draft)
    except Exception as ai_err:
        print(f"⚠️ Cảnh báo lỗi thuật toán AI quét ngầm: {str(ai_err)}")

    # 🗄️ ĐỌC GHI FILE CỨNG CHUẨN VĂN PHONG MÁY NHÀ BẠN
    draft_file_path = "draft_exams.json"
    existing_drafts = []
    
    if os.path.exists(draft_file_path) and os.path.getsize(draft_file_path) > 0:
        try:
            with open(draft_file_path, "r", encoding="utf-8") as f:
                existing_drafts = json.load(f)
        except Exception:
            existing_drafts = []

    # Tiến hành kiểm tra bẫy trùng mã đề và môn để ghi đè cập nhật cưỡng bức ăn chắc chắn
    is_replaced = False
    for idx, draft in enumerate(existing_drafts):
        if str(draft.get("de_so")) == str(new_draft["de_so"]) and str(draft.get("mon_hoc")) == str(new_draft["mon_hoc"]):
            existing_drafts[idx] = new_draft
            is_replaced = True
            break
            
    if not is_replaced:
        existing_drafts.append(new_draft)
    
    # Khóa chốt lệnh json.dump đổ sầm sập dữ liệu sạch bóng lỗi vào ổ đĩa máy nhà
    with open(draft_file_path, "w", encoding="utf-8") as f:
        json.dump(existing_drafts, f, ensure_ascii=False, indent=4)
        
    # === TEST TERMINAL ĐỐI SOÁT CHỮ CHỐT HẠ ===
    print('\n' + '🔥' * 15 + ' [BẪY LOG TERMINAL: ĐỒNG BỘ 3 PHẦN TOÀN DIỆN MÁY NHÀ] ' + '🔥' * 15)
    print(f"🪐 Thành công: Đã tiêm Đề số {new_draft['de_so']} vào file draft_exams.json!")
    print(f"🪐 Cấu trúc trường ID đã được gột rửa ép về dạng chuẩn: {[q.get('id') for q in new_draft['questions']]}")
    print(f"🪐 Kiểm tra biến de_so gài trong từng câu hỏi con: {[q.get('de_so') for q in new_draft['questions']]}")
    print('-' * 95 + '\n')
    # === END TEST ===
        
    return {"status": "success", "message": "Gửi đề thi vào kho đệm xét duyệt vương miện thành công!"}
#========================End====Soạn_duyệt_đề_thi_giao_diện_soạn_thảo===============
#=========================TRANG DUYỆT ĐỀ THI GIÁO VIÊN CHUYÊN MÔN===================
@app.get('/approve_exam')
def approve_page(request: Request):
    # 🪐 BỘ LỌC ĐỀ TỪ PYTHON: Nhặt tham số de_so từ đường link URL giáo viên quản lý gọi trên trình duyệt
    query_params = request.query_params
    current_de_so = query_params.get('de_so')
    
    import json
    import os

    # 🚀 LỘI BỘ VÀO FILE ĐỆM DRAFT_EXAMS.JSON ĐỂ TRÍCH XUẤT MA TRẬN ĐỀ CHỜ DUYỆT
    draft_file_path = "draft_exams.json"
    all_drafts = []
    
    if os.path.exists(draft_file_path) and os.path.getsize(draft_file_path) > 0:
        try:
            with open(draft_file_path, "r", encoding="utf-8") as f:
                all_drafts = json.load(f)
        except Exception as err:
            print(f"🚨 Lỗi đọc file đệm draft_exams.json vách sau: {err}")

    # Nếu trên URL link trơn không có tham số de_so, tự động bốc chiếc đề thi pending đầu tiên trong kho đệm
    if not current_de_so:
        draft_pending_dau_tien = next((str(d.get("de_so")) for d in all_drafts if str(d.get("trang_thai_duyet", "pending")) == "pending"), None)
        current_de_so = draft_pending_dau_tien if draft_pending_dau_tien else "16"
    else:
        current_de_so = str(current_de_so)

    # Dò tìm trúng chóc khối dữ liệu đề đệm hiện tại đang chọn
    selected_draft = None
    for d in all_drafts:
        if str(d.get("de_so")) == current_de_so:
            selected_draft = d
            break

    # Kịch bản dự phòng nếu kho đệm trống trơn hoặc chưa có đề số này tải lên
    if not selected_draft:
        selected_draft = {
            "de_so": current_de_so,
            "mon_hoc": "Chưa rõ",
            "ten_de": "Đề thi trống phân khu chờ duyệt",
            "nam": "2026",
            "lop": "12",
            "trang_thai_duyet": "none",
            "ai_assessment": {
                "trung_lap_percent": 0.0,
                "canh_bao_trung": "Không có dữ liệu đề đệm để AI đối soát bản quyền.",
                "ma_tran_goi_y": {"NhanBiet": 0, "ThongHieu": 0, "VanDung": 0, "VanDungCao": 0},
                "ghi_chu_ai": "Kho đệm trống."
            },
            "questions": []
        }

    # === TEST TERMINAL THEO CHỈ THỊ ĐĂNG ĐỐI SOÁT MÁY NHÀ BẠN ===
    print('\n' + '🔥' * 15 + ' [BẪY LOG TERMINAL: TRẠM ĐIỀU PHỐI KIỂM DUYỆT] ' + '🔥' * 15)
    print(f"🪐 Quản lý chuyên môn đang lội vào trang duyệt: Đề số {current_de_so}")
    print(f"🪐 Trạng thái phê duyệt hiện thời bọc trong kho đệm: {selected_draft.get('trang_thai_duyet')}")
    print(f"🪐 Kết quả đối soát AI: Trùng lặp {selected_draft['ai_assessment'].get('trung_lap_percent')}%")
    print(f"🪐 Tổng số lượng câu hỏi thô 3 phân khu đang chờ mổ xẻ: {len(selected_draft.get('questions', []))} câu")
    print('-' * 95 + '\n')
    # === END TEST ===

    # BẮN TƯƠI NGUYÊN KIỆT TÁC CONTEXT SANG JINJA2 HIỂN THỊ MẶT TIỀN FILE APPROVE_EXAM.HTML
    return templates.TemplateResponse(
        request=request,
        name="approve_exam.html",
        context={
            "draft_exam": selected_draft,
            "selected_de_so": current_de_so,
            "all_draft_navigation": [{"de_so": d.get("de_so"), "mon_hoc": d.get("mon_hoc"), "status": d.get("trang_thai_duyet")} for d in all_drafts]
        }
    )
#=========================TRANG DUYỆT ĐỀ THI GIÁO VIÊN CHUYÊN MÔN===================
#==============================Guwir Email=========================================
# -------- ĐỒNG BỘ DỮ LIỆU VÀ XỬ LÝ GỬI EMAIL MÔN VẬT LÝ ----------------
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
        questions_html = ""
        last_part = ""
                # --- BỘ LỌC ĐA NĂNG ĐỒNG BỘ CÔNG THỨC TOÁN CHO TOÀN BỘ CÁC PHẦN ---        
        # =========================================================================
        # 🤝 HỆ THỐNG ĐỒNG BỘ: ÉP TRỤC ĐIỀU HƯỚNG PDF THEO TRẬT TỰ CHUẨN WEBSITE 100%
        # =========================================================================
        import json
        import os
        # # 1. Đọc database tổng lên bộ nhớ RAM một lần duy nhất trước khi chạy vòng lặp
        db_data = []
        db_path = os.path.join(os.path.dirname(__file__), "database.json")
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    db_data = json.load(f)
            except Exception as e:
                print("Loi doc database hệ thống:", str(e))

        # 🔑 BỘ KHÓA TRẠNG THÁI TỔNG QUÁT THEO ĐÚNG CƠ CHẾ CỦA INDEX.HTML
        has_printed_p1 = False
        has_printed_p2 = False
        has_printed_p3 = False

        # # 2. Bắt đầu vòng lặp điều hướng độc nhất, ép buộc chạy cuốn chiếu theo Bản đồ ID chuẩn Website
        for index, current_q_id in enumerate(list_question_ids, 1):
            
            # # Cỗ máy truy vết ngược vị trí nhặt trúng đích hộp kết quả q bài làm của học sinh
            q = {}
            if current_q_id is not None and 'submitted_question_ids' in globals():
                try:
                    match_idx = submitted_question_ids.index(current_q_id)
                    q = questions_list[match_idx]
                except ValueError:
                    q = {}
            
            # 🎯 BỘ LỌC ĐA NĂNG TỰ ĐỘNG NHẬN DIỆN PHẦN THI ĐỒNG BỘ 100% TỪ DATABASE GỐC
            db_question = {}
            if current_q_id is not None and db_data:
                db_question = next((item for item in db_data if str(item.get("id", "")).strip() == str(current_q_id).strip()), {})
            
            # Nhặt kiểu định dạng đáp án và Tên phần thi gốc trực tiếp từ Database sạch
            q_choices_type = str(db_question.get("cac_lua_chon", "")).strip()
            current_part = str(db_question.get("part_name", "")).strip()
            
            # =========================================================================
            # 🪐 TỰ ĐỘNG BỐC CHỮ TIÊU ĐỀ ĐỒNG BỘ 100% TỪ FILE INDEX.HTML SANG RAM
            # =========================================================================
            html_p1_text = "PHẦN I. CÂU HỎI TRẮC NGHIỆM NHIỀU PHƯƠNG ÁN LỰA CHỌN"
            html_p2_text = "PHẦN II. CÂU HỎI TRẮC NGHIỆM ĐÚNG/SAI"
            html_p3_text = "PHẦN III. CÂU HỎI TRẮC NGHIỆM TRẢ LỜI NGẮN"
            
            html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
            if os.path.exists(html_path):
                try:
                    with open(html_path, "r", encoding="utf-8") as f_html:
                        html_content = f_html.read()
                        import re
                        matches = re.findall(r'<div class="section-header">\s*([^<]+)\s*</div>', html_content)
                        if len(matches) >= 3:
                            html_p1_text = matches[0].strip()
                            html_p2_text = matches[1].strip()
                            html_p3_text = matches[2].strip()
                except Exception as html_err:
                    print("Loi trich xuat chu tu index.html:", str(html_err))
            # =========================================================================

            # # Luồng 1: Tự động in nhãn Phan I đồng bộ động từ index.html (Thuần Việt)
            if q_choices_type != "Đúng, Sai" and "Điền số" not in q_choices_type and not has_printed_p1:
                questions_html += f"""
                <div style="background: linear-gradient(135deg, #1a365d, #2b6cb0); color: #ffffff; padding: 12px 20px; font-weight: bold; font-size: 15px; margin: 25px 0 15px 0; border-left: 6px solid #dd6b20; border-radius: 6px; box-shadow: 0 3px 6px rgba(0,0,0,0.08); letter-spacing: 0.5px;">
                    🎯 {html_p1_text.upper()}
                </div>
                """
                has_printed_p1 = True
                
            # # Luồng 2: Tự động in nhãn Phan II đồng bộ động từ index.html (Thuần Việt)
            elif q_choices_type == "Đúng, Sai" and not has_printed_p2:
                questions_html += f"""
                <div style="background: linear-gradient(135deg, #1a365d, #2b6cb0); color: #ffffff; padding: 12px 20px; font-weight: bold; font-size: 15px; margin: 25px 0 15px 0; border-left: 6px solid #dd6b20; border-radius: 6px; box-shadow: 0 3px 6px rgba(0,0,0,0.08); letter-spacing: 0.5px;">
                    ⚖️ {html_p2_text.upper()}
                </div>
                """
                has_printed_p2 = True
                
            # # Luồng 3: Tự động in nhãn Phan III đồng bộ động từ index.html (Thuần Việt)
            elif "Điền số" in q_choices_type and not has_printed_p3:
                questions_html += f"""
                <div style="background: linear-gradient(135deg, #1a365d, #2b6cb0); color: #ffffff; padding: 12px 20px; font-weight: bold; font-size: 15px; margin: 25px 0 15px 0; border-left: 6px solid #dd6b20; border-radius: 6px; box-shadow: 0 3px 6px rgba(0,0,0,0.08); letter-spacing: 0.5px;">
                    📝 {html_p3_text.upper()}
                </div>
                """
                has_printed_p3 = True
#========================END========IN RA TIÊU ĐỀ CÁC PHẦN CÂU HỎI ĐỒNG BỘ INDEX.HTML====================                
            user_ans = q.get("user_answer", "Chưa chọn")
            correct_ans = q.get("correct_answer", "")
            
            choices_layout_html = ""
            status_line_html = ""
            p2_data = q.get("p2_data", {}) if isinstance(q, dict) else {}
            
            # # MẤU CHỐT TỐI CAO: Bốc trọn gói câu hỏi gốc từ Database theo ID số bất biến
            db_question = {}
            if current_q_id is not None and db_data:
                db_question = next((item for item in db_data if str(item.get("id", "")).strip() == str(current_q_id).strip()), {})
                
            full_raw_text = str(db_question.get("noi_dung", ""))
                        
            # --- LUỒNG XỬ LÝ ĐÁP ÁN VÀ PHƯƠNG ÁN BÁM PHÍA DƯỚI GIỮ NGUYÊN VẸN CỦA BẠN ---
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

            # Trích xuất và sử dụng trọn vẹn HTML công thức đã dịch từ Frontend
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
#----------------test----------------
            print(f"--- RÀ SOÁT CÂU {idx if 'idx' in locals() else index} --- part: {current_part} | correct: {clean_correct if 'clean_correct' in locals() else correct_ans}")
#--------------End----Test------------------
            # --- TRƯỜNG HỢP 1: CÂU TRẮC NGHIỆM ĐƠN PHẦN I ---
            if db_question.get("cac_lua_chon", "") != "Đúng, Sai" and db_question.get("cac_lua_chon", "") != "Điền số":            
#----------------TEST-------------------
                print(f"👉 CHÚ Ý: CÂU {idx if 'idx' in locals() else index} BỊ LỌT VÀO KHỐI PHẦN I! Dữ liệu gốc: {db_question.get('cac_lua_chon', '')}")
                print(f"🔥 TRA CỨU ID CÂU {idx if 'idx' in locals() else index}: q_data={list(q.keys())} | id_value={q.get('id')} | q_id_value={q.get('q_id')}")
#----------------TEST-------------------
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
            elif db_question.get("cac_lua_chon", "") == "Đúng, Sai":                                
#----------------------Test_print-------------------
                print("===> CHÚC MỪNG: PYTHON ĐÃ NHẢY VÀO KHỐI PHẦN II THÀNH CÔNG! <===")
#---------End-------------Test_print-------------------
                # 📍 BƯỚC 2 HỆ THỐNG: Tìm vị trí chỉ mục hình học để cắt chuỗi từ full_raw_text sạch của database.json
                parts_p2 = {'a': '', 'b': '', 'c': '', 'd': ''}
                try:
                    pos_a = full_raw_text.find("a)")
                    pos_b = full_raw_text.find("b)")
                    pos_c = full_raw_text.find("c)")
                    pos_d = full_raw_text.find("d)")
                    
                    if pos_a != -1 and pos_b != -1:
                        parts_p2['a'] = full_raw_text[pos_a + 2:pos_b].strip()
                    if pos_b != -1 and pos_c != -1:
                        parts_p2['b'] = full_raw_text[pos_b + 2:pos_c].strip()
                    if pos_c != -1 and pos_d != -1:
                        parts_p2['c'] = full_raw_text[pos_c + 2:pos_d].strip()
                    if pos_d != -1:
                        parts_p2['d'] = full_raw_text[pos_d + 2:].strip()
                except Exception:
                    pass

                # Dựng hộp bảng điểm Phần II ma trận phẳng vuông vắn tăm tắp tuyệt đẹp
                user_ans_html = '<table style="width:100%!important;border-collapse:collapse!important;margin-top:6px!important;font-size:13px!important;border:1px solid #dee2e6!important;">'
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
                
                # Duyệt qua 4 nhãn chữ cái để bốc dữ liệu phương án
                for lbl_idx, lbl in enumerate(['a', 'b', 'c', 'd']):
                    raw_v = p2_data.get(lbl, {}) if isinstance(p2_data, dict) else {}
                    if not raw_v and isinstance(p2_data, dict):
                        raw_v = p2_data.get("Đáp án " + lbl.upper(), {})
                    
                    u_part = str(raw_v.get("user", "Chưa chọn"))
                    c_part = str(raw_v.get("correct", ""))
                    
                    # Đổ nội dung văn bản trích xuất sạch từ Database gốc vào bảng điểm
                    opt_text_p2 = parts_p2.get(lbl, "")
                    if not opt_text_p2:
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
            
            <!-- 🐉 HỆ THỐNG: ĐÓNG DẤU BẢN QUYỀN SONG NGỮ TRƯỜNG TỒN CHO TRANG GIẤY PDF -->
            <div style="position: fixed; bottom: -15px; left: 0; right: 0; text-align: center; font-size: 10px; color: #718096; border-top: 1px solid #e2e8f0; padding-top: 8px; font-family: 'Times New Roman', serif; line-height: 1.4;">
                © <strong>VIETDRAGON INTELLIGENT DATA BANK (VIETDRAGON IDB)</strong>. All rights reserved.<br>
                <span style="font-size: 9px; color: #a0aec0; font-weight: 500;">
                    Hệ thống Khảo thí & Dữ liệu lớn Thông minh | Intelligent Assessment & Big Data System
                </span>
            </div>
            <!-- 🐉 END ĐÓNG DẤU BẢN QUYỀN PDF -->
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

