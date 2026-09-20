import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple

SYNONYM_CLUSTERS = {
    "meja": ["meja", "meja belajar", "meja dosen", "meja kantor", "meja tulis", "desk", "table", "meja kerja", "podium"],
    "kursi": ["kursi", "bangku", "tempat duduk", "kursi kuliah", "kursi lipat", "kursi kantor", "chair", "sofa", "kursi plastik"],
    "papan_tulis": ["papan tulis", "whiteboard", "blackboard", "papan", "smartboard"],
    "pintu": ["pintu", "pintu masuk", "pintu ruangan", "daun pintu", "kusen pintu", "door"],
    "jendela": ["jendela", "jendela kaca", "kaca jendela", "kusen jendela", "window", "ventilasi kaca"],
    "dinding": ["dinding", "tembok", "dinding beton", "partisi", "sekat", "wall"],
    "lantai": ["lantai", "ubin", "keramik", "lantai keramik", "floor", "vinyl"],
    "plafon": ["plafon", "langit-langit", "atap", "ceiling", "gypsum"],
    "proyektor": ["proyektor", "projector", "infocus", "layar proyektor", "screen", "lcd proyektor"],
    "ac": ["ac", "air conditioner", "pendingin ruangan", "ac split", "ac cassette"],
    "lampu": ["lampu", "pencahayaan", "bohlam", "lampu tl", "lampu neon", "lampu led", "armatur lampu"],
    "stopkontak": ["stopkontak", "stop kontak", "colokan", "colokan listrik", "soket", "outlet", "power outlet"],
    "saklar": ["saklar", "sakelar", "switch", "saklar lampu"],
    "tempat_sampah": ["tempat sampah", "tong sampah", "kotak sampah", "trash can", "dustbin"],
    "jam": ["jam dinding", "jam", "clock"],
    "ventilasi": ["ventilasi", "lubang angin", "exhaust fan", "grille ac", "roster"],
    "tirai": ["tirai", "gorden", "horden", "blind", "roller blind"]
}

STOPWORDS = {"sebuah", "suatu", "bagian", "elemen", "di", "pada", "ruangan", "terdapat", "ada", "yang", "dan", "serta"}

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    words = [w for w in text.split() if w and w not in STOPWORDS]
    return " ".join(words)

def get_cluster(word: str) -> str:
    norm = normalize_text(word)
    for cluster_name, synonyms in SYNONYM_CLUSTERS.items():
        for syn in synonyms:
            if syn in norm or norm in syn:
                return cluster_name
    return ""

def calculate_similarity(s1: str, s2: str) -> float:
    n1 = normalize_text(s1)
    n2 = normalize_text(s2)
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0

    c1 = get_cluster(n1)
    c2 = get_cluster(n2)
    if c1 and c2 and c1 == c2:
        return 0.90

    # Sequence Matcher
    seq_ratio = SequenceMatcher(None, n1, n2).ratio()

    # Token overlap Jaccard
    w1 = set(n1.split())
    w2 = set(n2.split())
    jaccard = len(w1 & w2) / max(len(w1 | w2), 1)

    # Substring containment bonus
    containment = 0.0
    if n1 in n2 or n2 in n1:
        containment = 0.85

    return max(seq_ratio, jaccard, containment)

def run_verification_engine(
    ground_truths: List[Dict[str, Any]],
    ai_objects: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Classifies detection results into 4 lecture categories:
    - Correct Detection
    - Missed Detection
    - False Detection
    - Misclassification
    """
    matched_gt_ids = set()
    matched_ai_indices = set()
    verification_records: List[Dict[str, Any]] = []

    # Build similarity matrix
    candidates = []
    for gt_idx, gt in enumerate(ground_truths):
        gt_name = gt.get("object_name", "")
        for ai_idx, ai in enumerate(ai_objects):
            ai_name = ai.get("name", "")
            sim = calculate_similarity(gt_name, ai_name)
            candidates.append((sim, gt_idx, ai_idx))

    # Sort candidate pairs by highest similarity
    candidates.sort(key=lambda x: x[0], reverse=True)

    # Greedy matching for Correct & Misclassified
    for sim, gt_idx, ai_idx in candidates:
        if gt_idx in matched_gt_ids or ai_idx in matched_ai_indices:
            continue

        gt = ground_truths[gt_idx]
        ai = ai_objects[ai_idx]
        gt_name = gt.get("object_name", "")
        ai_name = ai.get("name", "")

        if sim >= 0.70:
            matched_gt_ids.add(gt_idx)
            matched_ai_indices.add(ai_idx)
            verification_records.append({
                "ground_truth_id": gt.get("id"),
                "ground_truth_name": gt_name,
                "detected_name": ai_name,
                "status": "correct",
                "similarity_score": round(sim, 2),
                "notes": f"Match akurat: '{gt_name}' ↔ '{ai_name}'"
            })
        elif 0.35 <= sim < 0.70:
            # Check cluster mismatch for misclassification
            c_gt = get_cluster(gt_name)
            c_ai = get_cluster(ai_name)
            if c_gt and c_ai and c_gt != c_ai:
                matched_gt_ids.add(gt_idx)
                matched_ai_indices.add(ai_idx)
                verification_records.append({
                    "ground_truth_id": gt.get("id"),
                    "ground_truth_name": gt_name,
                    "detected_name": ai_name,
                    "status": "misclassified",
                    "similarity_score": round(sim, 2),
                    "notes": f"Salah klasifikasi: GT '{gt_name}' diidentifikasi AI sebagai '{ai_name}'"
                })

    # Ground Truths without match => Missed Detection
    for gt_idx, gt in enumerate(ground_truths):
        if gt_idx not in matched_gt_ids:
            verification_records.append({
                "ground_truth_id": gt.get("id"),
                "ground_truth_name": gt.get("object_name", ""),
                "detected_name": None,
                "status": "missed",
                "similarity_score": 0.0,
                "notes": f"Objek ada di ruangan tetapi terlewat oleh AI: '{gt.get('object_name')}'"
            })

    # AI detections without match => False Detection (Hallucination)
    for ai_idx, ai in enumerate(ai_objects):
        if ai_idx not in matched_ai_indices:
            verification_records.append({
                "ground_truth_id": None,
                "ground_truth_name": None,
                "detected_name": ai.get("name", ""),
                "status": "false_detection",
                "similarity_score": 0.0,
                "notes": f"AI mendeteksi objek yang tidak tercatat di Ground Truth: '{ai.get('name')}'"
            })

    # Calculate summary metrics
    total_gt = len(ground_truths)
    total_ai = len(ai_objects)
    correct_count = sum(1 for r in verification_records if r["status"] == "correct")
    missed_count = sum(1 for r in verification_records if r["status"] == "missed")
    false_count = sum(1 for r in verification_records if r["status"] == "false_detection")
    misclassified_count = sum(1 for r in verification_records if r["status"] == "misclassified")

    accuracy = (correct_count / total_gt * 100) if total_gt > 0 else 0.0
    detection_rate = ((total_gt - missed_count) / total_gt * 100) if total_gt > 0 else 0.0

    return {
        "summary": {
            "total_ground_truth": total_gt,
            "total_ai_detected": total_ai,
            "correct_detection": correct_count,
            "missed_detection": missed_count,
            "false_detection": false_count,
            "misclassification": misclassified_count,
            "accuracy_percent": round(accuracy, 1),
            "detection_rate_percent": round(detection_rate, 1)
        },
        "records": verification_records
    }
