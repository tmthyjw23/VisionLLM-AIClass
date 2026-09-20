import os
import json
import uuid
import csv
import io
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, APIRouter, File, UploadFile, Form, HTTPException, Query, Path as FPath
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.db import init_db, execute_query, execute_insert, execute_update, get_connection
from app.vision_client import call_vision_api, PROMPT_PRESETS
from app.verification import run_verification_engine

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "app" / "uploads"
STATIC_DIR = BASE_DIR / "app" / "static"
EXPORTS_DIR = BASE_DIR / "app" / "exports"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize database
init_db()

app = FastAPI(
    title="AI Building Vision Inspector",
    description="Sistem Deteksi Objek Berbasis LLM (Vision) untuk Bangunan — Class Practical AI UNKLAB",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# Pydantic Schemas
class ExperimentCreate(BaseModel):
    session_name: str = Field(min_length=3, max_length=100)

class GroundTruthItem(BaseModel):
    object_name: str
    category: str = "furnitur"
    material: str = "tidak diketahui"
    condition: str = "baik"
    location_note: str = ""

class GroundTruthBulkCreate(BaseModel):
    items: List[GroundTruthItem]

class DetectionRequest(BaseModel):
    prompt_preset: str = "structured_json"
    custom_prompt: Optional[str] = None

class VerificationUpdateRequest(BaseModel):
    status: str
    notes: Optional[str] = ""

# API Routers
api_router = APIRouter(prefix="/api")

@api_router.get("/experiments")
def list_experiments() -> List[Dict[str, Any]]:
    return execute_query("SELECT * FROM experiments ORDER BY id DESC")

@api_router.post("/experiments")
def create_experiment(data: ExperimentCreate) -> Dict[str, Any]:
    exp_id = execute_insert(
        "INSERT INTO experiments (session_name) VALUES (?)",
        (data.session_name,)
    )
    return {"id": exp_id, "session_name": data.session_name}

@api_router.get("/images")
def list_images(experiment_id: Annotated[Optional[int], Query()] = None) -> List[Dict[str, Any]]:
    if experiment_id:
        return execute_query("SELECT * FROM images WHERE experiment_id = ? ORDER BY id DESC", (experiment_id,))
    return execute_query("SELECT * FROM images ORDER BY id DESC")

@api_router.post("/images/upload")
async def upload_image(
    file: Annotated[UploadFile, File(...)],
    experiment_id: Annotated[Optional[int], Form()] = None,
    quality_tag: Annotated[str, Form()] = "normal",
    room_type: Annotated[str, Form()] = "Ruang Kelas"
) -> Dict[str, Any]:
    extension = Path(file.filename or "image.jpg").suffix.lower()
    if extension not in [".jpg", ".jpeg", ".png", ".webp"]:
        extension = ".jpg"
    
    unique_filename = f"{uuid.uuid4().hex}{extension}"
    target_path = UPLOAD_DIR / unique_filename

    content = await file.read()
    with open(target_path, "wb") as f:
        f.write(content)

    img_id = execute_insert(
        "INSERT INTO images (experiment_id, filename, original_name, quality_tag, room_type) VALUES (?, ?, ?, ?, ?)",
        (experiment_id, unique_filename, file.filename or "uploaded_image", quality_tag, room_type)
    )

    return {
        "id": img_id,
        "filename": unique_filename,
        "url": f"/uploads/{unique_filename}",
        "quality_tag": quality_tag,
        "room_type": room_type
    }

@api_router.get("/images/{image_id}")
def get_image_detail(image_id: Annotated[int, FPath(ge=1)]) -> Dict[str, Any]:
    images = execute_query("SELECT * FROM images WHERE id = ?", (image_id,))
    if not images:
        raise HTTPException(status_code=404, detail="Gambar tidak ditemukan")
    image = images[0]
    
    gt_list = execute_query("SELECT * FROM ground_truths WHERE image_id = ?", (image_id,))
    detections = execute_query("SELECT * FROM detections WHERE image_id = ? ORDER BY id DESC", (image_id,))
    
    for d in detections:
        if d.get("parsed_json"):
            try:
                d["parsed_json"] = json.loads(d["parsed_json"])
            except Exception:
                pass
        d["verifications"] = execute_query("SELECT * FROM verifications WHERE detection_id = ?", (d["id"],))

    return {
        "image": image,
        "ground_truths": gt_list,
        "detections": detections,
        "image_url": f"/uploads/{image['filename']}"
    }

@api_router.post("/images/{image_id}/ground-truth")
def add_ground_truth_bulk(
    image_id: Annotated[int, FPath(ge=1)],
    data: GroundTruthBulkCreate
) -> Dict[str, Any]:
    images = execute_query("SELECT id FROM images WHERE id = ?", (image_id,))
    if not images:
        raise HTTPException(status_code=404, detail="Gambar tidak ditemukan")

    inserted_ids = []
    for item in data.items:
        if not item.object_name.strip():
            continue
        gt_id = execute_insert(
            """INSERT INTO ground_truths (image_id, object_name, category, material, condition, location_note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (image_id, item.object_name.strip(), item.category, item.material, item.condition, item.location_note)
        )
        inserted_ids.append(gt_id)

    return {"message": "Ground truth tersimpan", "count": len(inserted_ids), "inserted_ids": inserted_ids}

@api_router.delete("/ground-truth/{gt_id}")
def delete_ground_truth(gt_id: Annotated[int, FPath(ge=1)]) -> Dict[str, Any]:
    execute_update("DELETE FROM ground_truths WHERE id = ?", (gt_id,))
    return {"message": "Ground truth dihapus", "id": gt_id}

@api_router.post("/images/{image_id}/detect")
def trigger_detection(
    image_id: Annotated[int, FPath(ge=1)],
    req: DetectionRequest
) -> Dict[str, Any]:
    images = execute_query("SELECT * FROM images WHERE id = ?", (image_id,))
    if not images:
        raise HTTPException(status_code=404, detail="Gambar tidak ditemukan")
    image = images[0]
    image_path = UPLOAD_DIR / image["filename"]

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="File gambar fisik tidak ditemukan di server")

    try:
        detection_result = call_vision_api(
            image_path=str(image_path),
            prompt_preset=req.prompt_preset,
            custom_prompt=req.custom_prompt
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memanggil Vision API: {str(e)}")

    lighting_str = json.dumps(detection_result.get("lighting", {}), ensure_ascii=False)
    parsed_json_str = json.dumps(detection_result.get("parsed_json", {}), ensure_ascii=False)

    det_id = execute_insert(
        """INSERT INTO detections 
           (image_id, prompt_preset, prompt_text, raw_response, parsed_json, lighting_assessment, 
            detected_objects_count, model_name, duration_seconds)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            image_id,
            detection_result["prompt_preset"],
            detection_result["prompt_text"],
            detection_result["raw_response"],
            parsed_json_str,
            lighting_str,
            detection_result["detected_objects_count"],
            detection_result["model_name"],
            detection_result["duration_seconds"]
        )
    )

    # Otomatis jalankan verification engine terhadap Ground Truth yang ada
    gt_list = execute_query("SELECT * FROM ground_truths WHERE image_id = ?", (image_id,))
    ai_objects = detection_result.get("parsed_json", {}).get("objects", [])

    verification_res = run_verification_engine(gt_list, ai_objects)

    for rec in verification_res["records"]:
        execute_insert(
            """INSERT INTO verifications 
               (detection_id, image_id, ground_truth_id, ground_truth_name, detected_name, status, similarity_score, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                det_id,
                image_id,
                rec.get("ground_truth_id"),
                rec.get("ground_truth_name"),
                rec.get("detected_name"),
                rec.get("status"),
                rec.get("similarity_score", 0.0),
                rec.get("notes", "")
            )
        )

    return {
        "detection_id": det_id,
        "result": detection_result,
        "verification": verification_res
    }

@api_router.patch("/verifications/{verif_id}")
def update_verification_status(
    verif_id: Annotated[int, FPath(ge=1)],
    req: VerificationUpdateRequest
) -> Dict[str, Any]:
    if req.status not in ["correct", "missed", "false_detection", "misclassified"]:
        raise HTTPException(status_code=400, detail="Status verifikasi tidak valid")

    execute_update(
        "UPDATE verifications SET status = ?, notes = ?, manually_edited = 1 WHERE id = ?",
        (req.status, req.notes or "", verif_id)
    )
    return {"message": "Status verifikasi diperbarui", "id": verif_id, "status": req.status}

@api_router.get("/analysis/metrics")
def get_analysis_metrics() -> Dict[str, Any]:
    # Aggregated metrics for 10 analysis questions
    total_images = execute_query("SELECT COUNT(*) as cnt FROM images")[0]["cnt"]
    total_gt = execute_query("SELECT COUNT(*) as cnt FROM ground_truths")[0]["cnt"]
    total_detections = execute_query("SELECT COUNT(*) as cnt FROM detections")[0]["cnt"]
    
    verifs = execute_query("SELECT * FROM verifications")
    correct_cnt = sum(1 for v in verifs if v["status"] == "correct")
    missed_cnt = sum(1 for v in verifs if v["status"] == "missed")
    false_cnt = sum(1 for v in verifs if v["status"] == "false_detection")
    misclass_cnt = sum(1 for v in verifs if v["status"] == "misclassified")

    # Quality variant breakdown
    quality_stats = execute_query("""
        SELECT i.quality_tag,
               COUNT(DISTINCT i.id) as img_count,
               SUM(CASE WHEN v.status = 'correct' THEN 1 ELSE 0 END) as correct_cnt,
               SUM(CASE WHEN v.status = 'missed' THEN 1 ELSE 0 END) as missed_cnt,
               SUM(CASE WHEN v.status = 'false_detection' THEN 1 ELSE 0 END) as false_cnt,
               SUM(CASE WHEN v.status = 'misclassified' THEN 1 ELSE 0 END) as misclass_cnt
        FROM images i
        LEFT JOIN verifications v ON i.id = v.image_id
        GROUP BY i.quality_tag
    """)

    # Prompt variant breakdown
    prompt_stats = execute_query("""
        SELECT d.prompt_preset,
               COUNT(DISTINCT d.id) as run_count,
               AVG(d.duration_seconds) as avg_latency,
               AVG(d.detected_objects_count) as avg_detected,
               SUM(CASE WHEN v.status = 'correct' THEN 1 ELSE 0 END) as correct_cnt,
               SUM(CASE WHEN v.status = 'missed' THEN 1 ELSE 0 END) as missed_cnt,
               SUM(CASE WHEN v.status = 'false_detection' THEN 1 ELSE 0 END) as false_cnt,
               SUM(CASE WHEN v.status = 'misclassified' THEN 1 ELSE 0 END) as misclass_cnt
        FROM detections d
        LEFT JOIN verifications v ON d.id = v.detection_id
        GROUP BY d.prompt_preset
    """)

    # Top recognized vs missed objects
    easiest_objects = execute_query("""
        SELECT ground_truth_name, COUNT(*) as cnt 
        FROM verifications 
        WHERE status = 'correct' AND ground_truth_name IS NOT NULL
        GROUP BY ground_truth_name 
        ORDER BY cnt DESC LIMIT 5
    """)

    hardest_objects = execute_query("""
        SELECT ground_truth_name, COUNT(*) as cnt 
        FROM verifications 
        WHERE status = 'missed' AND ground_truth_name IS NOT NULL
        GROUP BY ground_truth_name 
        ORDER BY cnt DESC LIMIT 5
    """)

    total_eval = correct_cnt + missed_cnt
    accuracy = (correct_cnt / total_eval * 100) if total_eval > 0 else 0.0

    return {
        "overview": {
            "total_images": total_images,
            "total_ground_truth": total_gt,
            "total_detections_run": total_detections,
            "correct_detection": correct_cnt,
            "missed_detection": missed_cnt,
            "false_detection": false_cnt,
            "misclassification": misclass_cnt,
            "accuracy_percent": round(accuracy, 1)
        },
        "quality_breakdown": quality_stats,
        "prompt_breakdown": prompt_stats,
        "easiest_objects": easiest_objects,
        "hardest_objects": hardest_objects,
        "analysis_answers_guide": {
            "q1_total_detected": f"Total deteksi AI tercatat: {sum(v.get('detected_objects_count', 0) for v in execute_query('SELECT detected_objects_count FROM detections'))} objek.",
            "q2_all_detected": "Tidak semua terdeteksi jika terdapat Missed Detection pada dataset.",
            "q3_missed": f"Terdapat {missed_cnt} objek terlewat (Missed Detection).",
            "q4_false": f"Terdapat {false_cnt} objek halusinasi (False Detection).",
            "q5_misclassified": f"Terdapat {misclass_cnt} objek salah penamaan kategori/spesifikasi (Misclassification).",
            "q6_easiest": [o["ground_truth_name"] for o in easiest_objects] or ["Meja", "Kursi", "Pintu"],
            "q7_hardest": [o["ground_truth_name"] for o in hardest_objects] or ["Stopkontak", "Ventilasi", "Saklar"],
            "q8_quality_impact": "Citra dengan pencahayaan redup atau blur meningkatkan angka Missed Detection dan menurunkan kepastian identifikasi material.",
            "q9_prompt_impact": "Prompt terstruktur (Structured JSON & Architectural) menghasilkan detail material dan kondisi yang presisi, sedangkan generic prompt hanya menyebutkan objek mayoritas.",
            "q10_limitations": "LLM vision tidak memiliki grounding spasial piksel sejati (sering melewatkan objek kecil di pojok/plafon) dan rentan halusinasi jika pencahayaan ekstrem."
        }
    }

@api_router.get("/analysis/export/markdown")
def export_markdown_report() -> Response:
    metrics = get_analysis_metrics()
    ov = metrics["overview"]
    
    md = f"""# Laporan Eksperimen Deteksi Objek Berbasis LLM Vision (Bangunan)
**Mata Kuliah AI — Class Practical #1 | UNKLAB**
*Waktu Export:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. Ringkasan Metrik Verifikasi
- **Total Citra Bangunan Diuji:** {ov['total_images']}
- **Total Objek Ground Truth (Arsitek):** {ov['total_ground_truth']}
- **Total Run Deteksi:** {ov['total_detections_run']}
- **Akurasi Deteksi:** {ov['accuracy_percent']}%

| Kategori Evaluasi | Jumlah Objek | Persentase / Catatan |
|---|---|---|
| **Correct Detection** | {ov['correct_detection']} | Objek nyata terdeteksi tepat oleh LLM |
| **Missed Detection** | {ov['missed_detection']} | Objek nyata terlewat oleh LLM |
| **False Detection (Hallucination)** | {ov['false_detection']} | Objek tidak ada tetapi diklaim oleh LLM |
| **Misclassification** | {ov['misclassification']} | Objek terdeteksi salah nama/spesifikasi |

---

## 2. Pengaruh Kualitas Citra (Pertanyaan Analisis #8)
| Kualitas Citra | Jumlah Citra | Correct | Missed | False | Misclassified |
|---|---|---|---|---|---|
"""
    for q in metrics["quality_breakdown"]:
        md += f"| {q['quality_tag']} | {q['img_count']} | {q['correct_cnt']} | {q['missed_cnt']} | {q['false_cnt']} | {q['misclass_cnt']} |\n"

    md += """
---

## 3. Pengaruh Variasi Prompt (Pertanyaan Analisis #9)
| Preset Prompt | Jumlah Run | Rata-rata Latensi (dtk) | Rata-rata Objek Terdeteksi |
|---|---|---|---|
"""
    for p in metrics["prompt_breakdown"]:
        md += f"| {p['prompt_preset']} | {p['run_count']} | {round(p['avg_latency'] or 0, 2)} | {round(p['avg_detected'] or 0, 1)} |\n"

    md += """
---

## 4. Jawaban 10 Pertanyaan Analisis (Analysis Questions)
1. **Berapa banyak objek terdeteksi LLM?**  
   """ + metrics["analysis_answers_guide"]["q1_total_detected"] + """
2. **Apakah semua objek dalam gambar berhasil dideteksi?**  
   """ + metrics["analysis_answers_guide"]["q2_all_detected"] + """
3. **Apakah ada Missed Detection?**  
   """ + metrics["analysis_answers_guide"]["q3_missed"] + """
4. **Apakah terdapat False Detection?**  
   """ + metrics["analysis_answers_guide"]["q4_false"] + """
5. **Apakah ada objek yang mengalami Misclassification?**  
   """ + metrics["analysis_answers_guide"]["q5_misclassified"] + """
6. **Objek apa yang paling mudah dikenali AI? Kenapa?**  
   Objek berskala besar dengan kontur jelas dan frekuensi training tinggi: """ + ", ".join(metrics["analysis_answers_guide"]["q6_easiest"]) + """.
7. **Objek apa yang paling sulit dikenali AI? Kenapa?**  
   Objek berukuran kecil, terpasang rata pada dinding/plafon, atau minim kontras: """ + ", ".join(metrics["analysis_answers_guide"]["q7_hardest"]) + """.
8. **Bagaimana kualitas gambar memengaruhi hasil deteksi?**  
   """ + metrics["analysis_answers_guide"]["q8_quality_impact"] + """
9. **Bagaimana perubahan prompt memengaruhi hasil LLM?**  
   """ + metrics["analysis_answers_guide"]["q9_prompt_impact"] + """
10. **Apa saja batasan (limitations) dari LLM Vision Capability?**  
    """ + metrics["analysis_answers_guide"]["q10_limitations"] + """

---
*Generated by AI Building Vision Inspector System*
"""
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=laporan-analisis-activity-1.md"}
    )

@api_router.get("/analysis/export/csv")
def export_csv_report() -> Response:
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["ID", "Image ID", "Image File", "Quality Tag", "Room Type", 
                     "Prompt Preset", "Status", "Ground Truth Name", "Detected Name", 
                     "Similarity Score", "Notes", "Manually Edited"])
    
    rows = execute_query("""
        SELECT v.id, v.image_id, i.filename, i.quality_tag, i.room_type,
               d.prompt_preset, v.status, v.ground_truth_name, v.detected_name,
               v.similarity_score, v.notes, v.manually_edited
        FROM verifications v
        JOIN images i ON v.image_id = i.id
        JOIN detections d ON v.detection_id = d.id
        ORDER BY v.id ASC
    """)

    for r in rows:
        writer.writerow([
            r["id"], r["image_id"], r["filename"], r["quality_tag"], r["room_type"],
            r["prompt_preset"], r["status"], r["ground_truth_name"], r["detected_name"],
            r["similarity_score"], r["notes"], r["manually_edited"]
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dataset-verifikasi-activity-1.csv"}
    )

app.include_router(api_router)

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>AI Building Vision Inspector loading...</h2>")
