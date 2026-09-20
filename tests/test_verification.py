import pytest
from app.verification import calculate_similarity, run_verification_engine

def test_similarity_exact_and_synonym():
    assert calculate_similarity("kursi", "kursi") == 1.0
    assert calculate_similarity("whiteboard", "papan tulis") >= 0.85
    assert calculate_similarity("meja belajar", "meja") >= 0.80
    assert calculate_similarity("jendela", "kucing") < 0.20

def test_verification_engine_all_four_categories():
    ground_truths = [
        {"id": 1, "object_name": "kursi mahasiswa", "category": "furnitur"},
        {"id": 2, "object_name": "meja dosen", "category": "furnitur"},
        {"id": 3, "object_name": "stopkontak dinding", "category": "elektrikal"},
        {"id": 4, "object_name": "papan tulis", "category": "perlengkapan"}
    ]

    ai_objects = [
        {"name": "kursi", "material": "kayu", "condition": "baik"},
        {"name": "meja", "material": "kayu", "condition": "baik"},
        {"name": "layar proyektor", "material": "kain", "condition": "baik"}, # Candidate misclassified or false
        {"name": "tanaman hias", "material": "organik", "condition": "baik"}   # False detection (not in room)
    ]

    result = run_verification_engine(ground_truths, ai_objects)
    summary = result["summary"]
    records = result["records"]

    # Verify Correct
    correct_names = [r["ground_truth_name"] for r in records if r["status"] == "correct"]
    assert "kursi mahasiswa" in correct_names
    assert "meja dosen" in correct_names

    # Verify Missed: stopkontak was not in AI output
    missed_names = [r["ground_truth_name"] for r in records if r["status"] == "missed"]
    assert "stopkontak dinding" in missed_names

    # Verify False Detection: tanaman hias is hallucinated
    false_names = [r["detected_name"] for r in records if r["status"] == "false_detection"]
    assert "tanaman hias" in false_names

    assert summary["total_ground_truth"] == 4
    assert summary["correct_detection"] >= 2
    assert summary["missed_detection"] >= 1
    assert summary["false_detection"] >= 1
