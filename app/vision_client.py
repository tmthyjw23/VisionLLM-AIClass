import os
import re
import json
import time
import base64
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

def load_env_vars():
    # Priority 1: environment variables (Vercel / serverless)
    # Priority 2: .env file (local dev)
    env_dict = {k: v for k, v in os.environ.items() if k.startswith(("VISION_", "OLLAMA_", "GEMINI_"))}
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    # Don't override env vars already set (env vars take precedence)
                    if k not in env_dict:
                        env_dict[k] = v
    return env_dict

ENV_CONFIG = load_env_vars()

PROMPT_PRESETS = {
    "generic": (
        "Identifikasi dan sebutkan semua objek yang dapat kamu lihat di dalam gambar ruangan interior bangunan ini. "
        "Sebutkan objek secara lugas dan jelas."
    ),
    "architectural": (
        "Bertindaklah sebagai ahli arsitektur dan inspektur bangunan interior. Analisis gambar interior ini secara mendalam:\n"
        "1. Identifikasi setiap objek dan elemen arsitektur (furnitur, dinding, jendela, pintu, plafon, lantai, partisi, stopkontak, saklar, dll).\n"
        "2. Identifikasi perkiraan material (kayu, beton, baja/logam, kaca, gypsum, kain, keramik, dll).\n"
        "3. Evaluasi kondisi fisik atau kerusakan (baik, retak, aus, kotor, rusak, berdebu).\n"
        "4. Analisis kualitas dan sumber pencahayaan ruangan (terang, redup, merata, tidak merata, alami/buatan).\n\n"
        "Formatkan jawaban Anda dalam JSON valid:\n"
        "{\n"
        '  "objects": [\n'
        '    {"name": "nama objek", "material": "material", "condition": "kondisi", "location": "posisi objek"}\n'
        "  ],\n"
        '  "lighting": {"quality": "terang/redup", "source": "alami/buatan", "uniformity": "merata/tidak merata", "description": "detail pencahayaan"},\n'
        '  "room_type": "ruang kelas / koridor / lab / dll",\n'
        '  "architectural_notes": "catatan arsitektural"\n'
        "}"
    ),
    "structured_json": (
        "Analisis gambar interior bangunan ini. Kembalikan HANYA format JSON murni tanpa markdown fence dan tanpa teks lain di luar JSON:\n"
        "{\n"
        '  "objects": [\n'
        '    {\n'
        '      "name": "nama objek spesifik",\n'
        '      "material": "kayu/beton/kaca/logam/plastik/lainnya",\n'
        '      "condition": "baik/aus/kotor/retak/rusak",\n'
        '      "location": "lokasi di gambar"\n'
        "    }\n"
        "  ],\n"
        '  "lighting": {\n'
        '    "quality": "terang/redup/cukup",\n'
        '    "description": "penjelasan pencahayaan"\n'
        "  },\n"
        '  "room_type": "tipe ruangan"\n'
        "}"
    )
}

def clean_json_string(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if match:
        return match.group(1).strip()
    return cleaned

def parse_llm_response(raw_text: str) -> Dict[str, Any]:
    cleaned = clean_json_string(raw_text)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and "objects" in parsed:
            return parsed
    except Exception:
        pass

    # Fallback parser for non-JSON or generic bullet list responses
    extracted_objects: List[Dict[str, Any]] = []
    lines = raw_text.splitlines()
    for line in lines:
        line = line.strip()
        # Look for bullet points or numbering: "- Kursi kantor", "1. Meja kayu"
        bullet_match = re.match(r"^(?:[\*\-•]|\d+[\.\)])\s*(.+)", line)
        if bullet_match:
            item_text = bullet_match.group(1).strip()
            # Split if there are colons, e.g. "Kursi: berbahan plastik, kondisi baik"
            parts = item_text.split(":")
            name = parts[0].strip()
            detail = parts[1].strip() if len(parts) > 1 else ""
            extracted_objects.append({
                "name": name,
                "material": "tidak disebutkan",
                "condition": "tidak disebutkan",
                "location": detail or "dalam ruangan"
            })

    # If still empty, attempt comma separation
    if not extracted_objects and len(raw_text.strip()) > 0:
        words = [w.strip() for w in re.split(r"[,;\n]", raw_text) if len(w.strip()) > 2]
        for w in words[:15]:
            extracted_objects.append({
                "name": w,
                "material": "tidak disebutkan",
                "condition": "tidak disebutkan",
                "location": "dalam ruangan"
            })

    return {
        "objects": extracted_objects,
        "lighting": {
            "quality": "tidak dianalisis spesifik",
            "description": "Respons LLM generik"
        },
        "room_type": "Interior Bangunan",
        "raw_fallback": True
    }

def call_vision_api(
    image_path: str,
    prompt_preset: str = "structured_json",
    custom_prompt: Optional[str] = None
) -> Dict[str, Any]:
    env = load_env_vars()
    base_url = env.get("VISION_BASE_URL", "http://localhost:20128/v1")
    api_key = env.get("VISION_API_KEY", "")
    if not api_key:
        raise ValueError("VISION_API_KEY tidak dikonfigurasi. Set di .env atau environment variable Vercel.")
    model_name = env.get("VISION_MODEL", "ag/gemini-3.8-flash-high")

    endpoint = f"{base_url.rstrip('/')}/chat/completions"

    prompt_text = custom_prompt if custom_prompt else PROMPT_PRESETS.get(prompt_preset, PROMPT_PRESETS["structured_json"])

    with open(image_path, "rb") as f:
        image_bytes = f.read()
    base64_img = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_img}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1200,
        "stream": False
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    start_time = time.time()
    response = requests.post(endpoint, headers=headers, json=payload, timeout=90)
    duration = time.time() - start_time
    response.raise_for_status()

    res_json = response.json()
    raw_content = res_json["choices"][0]["message"]["content"]

    parsed_result = parse_llm_response(raw_content)

    return {
        "prompt_preset": prompt_preset,
        "prompt_text": prompt_text,
        "raw_response": raw_content,
        "parsed_json": parsed_result,
        "model_name": model_name,
        "duration_seconds": round(duration, 2),
        "lighting": parsed_result.get("lighting", {}),
        "detected_objects_count": len(parsed_result.get("objects", []))
    }
