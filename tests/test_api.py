import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_api_list_experiments_and_create():
    res = client.get("/api/experiments")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res_post = client.post("/api/experiments", json={"session_name": "Test Sesi Arsitektur"})
    assert res_post.status_code == 200
    assert "id" in res_post.json()

def test_api_upload_and_ground_truth():
    # Test uploading a small synthetic dummy image
    image_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    files = {"file": ("test_room.jpg", image_bytes, "image/jpeg")}
    data = {"quality_tag": "normal", "room_type": "Ruang Kelas"}
    
    res = client.post("/api/images/upload", files=files, data=data)
    assert res.status_code == 200
    img_data = res.json()
    image_id = img_data["id"]
    assert image_id > 0

    # Add ground truth
    gt_payload = {
        "items": [
            {"object_name": "kursi", "category": "furnitur", "material": "kayu", "condition": "baik"},
            {"object_name": "papan tulis", "category": "arsitektur", "material": "kaca", "condition": "baik"}
        ]
    }
    res_gt = client.post(f"/api/images/{image_id}/ground-truth", json=gt_payload)
    assert res_gt.status_code == 200
    assert res_gt.json()["count"] == 2

    # Get image detail
    res_detail = client.get(f"/api/images/{image_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert len(detail["ground_truths"]) == 2

def test_api_analytics_and_export():
    res_metrics = client.get("/api/analysis/metrics")
    assert res_metrics.status_code == 200
    data = res_metrics.json()
    assert "overview" in data
    assert "analysis_answers_guide" in data

    res_md = client.get("/api/analysis/export/markdown")
    assert res_md.status_code == 200
    assert "Laporan Eksperimen" in res_md.text

    res_csv = client.get("/api/analysis/export/csv")
    assert res_csv.status_code == 200
    assert "Ground Truth Name" in res_csv.text

def test_slide_endpoints():
    res_slide_html = client.get("/slide.html")
    assert res_slide_html.status_code == 200
    assert "AI Building Vision Inspector" in res_slide_html.text
    assert "reveal" in res_slide_html.text

    res_slide = client.get("/slide")
    assert res_slide.status_code == 200
    assert "AI Building Vision Inspector" in res_slide.text
