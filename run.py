import sys
import uvicorn
from pathlib import Path

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if __name__ == "__main__":
    print("==================================================================")
    print("   AI Building Vision Inspector (Class Practical AI UNKLAB)      ")
    print("   Server running on: http://localhost:8000                      ")
    print("   API Docs on:       http://localhost:8000/docs                  ")
    print("==================================================================")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
