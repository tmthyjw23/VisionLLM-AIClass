import pytest
from app.vision_client import clean_json_string, parse_llm_response

def test_clean_json_string_with_code_fences():
    raw_fence = '```json\n{"objects": [{"name": "kursi"}]}\n```'
    cleaned = clean_json_string(raw_fence)
    assert cleaned == '{"objects": [{"name": "kursi"}]}'

def test_parse_llm_response_valid_json():
    raw = '```json\n{"objects": [{"name": "pintu", "material": "kayu", "condition": "baik", "location": "kiri"}], "lighting": {"quality": "terang"}}\n```'
    parsed = parse_llm_response(raw)
    assert len(parsed["objects"]) == 1
    assert parsed["objects"][0]["name"] == "pintu"
    assert parsed["lighting"]["quality"] == "terang"

def test_parse_llm_response_fallback_bullets():
    raw_bullets = """
    Berikut objek yang terdeteksi di ruangan:
    - Meja kerja: kayu kokoh
    - Kursi putar: warna hitam
    - Jendela kaca: pencahayaan masuk dari luar
    """
    parsed = parse_llm_response(raw_bullets)
    names = [o["name"] for o in parsed["objects"]]
    assert "Meja kerja" in names
    assert "Kursi putar" in names
    assert "Jendela kaca" in names
