import sys
from pathlib import Path

# Ensure project root is importable on Vercel (api/ is one level deep)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

# Vercel Python runtime expects `app` at module level
# No additional code needed - Vercel will serve via Mangum/ASGI
