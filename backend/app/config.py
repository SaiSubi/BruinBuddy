"""Settings, loaded from the environment and the repo-root .env (git-ignored)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

COURSE_DIR = ROOT / "18.05-spring-2022"
PDF_DIR = Path(os.getenv("BB_PDF_DIR") or COURSE_DIR / "static_resources")
META_DIR = COURSE_DIR / "resources"
DB_PATH = Path(os.getenv("BB_DB_PATH") or ROOT / "data" / "bruinbuddy.db")
FRONTEND_DIST = ROOT / "frontend" / "dist"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
TUTOR_MODEL = os.getenv("TUTOR_MODEL", "anthropic/claude-sonnet-5.5")
HELPER_MODEL = os.getenv("HELPER_MODEL", "anthropic/claude-haiku-5.5")
MOCK_LLM = os.getenv("BB_MOCK_LLM", "0") == "1"

TOP_K = 6
MIN_RETRIEVAL_SCORE = 3.0  # BM25 is not calibrated: this only drops near-empty matches; the tutor judges relevance
HISTORY_TURNS = 8
MAX_MEMORY_NOTES = 15
TUTOR_MAX_TOKENS = 1500
HELPER_MAX_TOKENS = 600

# ---- deployment / security -------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()          # Postgres (Supabase) in prod; SQLite if empty
PRODUCTION = os.getenv("ENV", "").lower() == "production"
SECRET_KEY = os.getenv("SECRET_KEY", "")                       # signs session and file tokens
STUDENT_CODE = os.getenv("STUDENT_CODE", "")                   # optional access code for students
PROFESSOR_CODE = os.getenv("PROFESSOR_CODE", "")               # required for professor sign-in in production
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", str(7 * 24 * 3600)))
FILE_TOKEN_TTL_SECONDS = 3600

# Supabase Storage holds the public (citable) PDFs in production; local dev reads them from PDF_DIR.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "course-pdfs")
DAILY_MESSAGE_LIMIT = int(os.getenv("DAILY_MESSAGE_LIMIT", "60"))      # per student, rolling 24h
GLOBAL_DAILY_LIMIT = int(os.getenv("GLOBAL_DAILY_LIMIT", "600"))       # all students, rolling 24h


def check_production_settings() -> None:
    """Refuse to boot in production with unsafe settings."""
    if not PRODUCTION:
        return
    problems = []
    if len(SECRET_KEY) < 32:
        problems.append("SECRET_KEY must be set to a random string of at least 32 characters")
    if not DATABASE_URL:
        problems.append("DATABASE_URL must be set (Postgres)")
    if MOCK_LLM:
        problems.append("BB_MOCK_LLM must not be enabled")
    if not OPENROUTER_API_KEY:
        problems.append("OPENROUTER_API_KEY must be set")
    if not (SUPABASE_URL and SUPABASE_SERVICE_KEY):
        problems.append("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set (PDF storage)")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
