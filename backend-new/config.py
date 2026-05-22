from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# ── MongoDB ──────────────────────────────────────────────
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']

# ── JWT ──────────────────────────────────────────────────
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"

# ── Demo credentials ─────────────────────────────────────
DEMO_EMAIL = os.environ.get('DEMO_EMAIL', 'demo@taskflow.com')
DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD', 'demo1234')

# ── Cloudinary ───────────────────────────────────────────
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')

# ── CORS ─────────────────────────────────────────────────
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
