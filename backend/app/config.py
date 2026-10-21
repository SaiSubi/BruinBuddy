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
UPLOAD_DIR = Path(os.getenv("BB_UPLOAD_DIR") or ROOT / "data" / "uploads")  # local dev; Supabase Storage in prod
FRONTEND_DIST = ROOT / "frontend" / "dist"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
TUTOR_MODEL = os.getenv("TUTOR_MODEL", "anthropic/claude-sonnet-5.5")
HELPER_MODEL = os.getenv("HELPER_MODEL", "anthropic/claude-haiku-5.5")
TUTOR_FALLBACK_MODEL = os.getenv("TUTOR_FALLBACK_MODEL", "").strip()  # tried once if the tutor fails before any text
MOCK_LLM = os.getenv("BB_MOCK_LLM", "0") == "1"
LLM_TIMEOUT_SECONDS = 60
SYNC_JOBS = os.getenv("BB_SYNC_JOBS", "0") == "1"  # tests: run background jobs inline

TOP_K = 6
MIN_RETRIEVAL_SCORE = 3.0  # BM25 is not calibrated: this only drops near-empty matches; the tutor judges relevance
HISTORY_TURNS = 8
MAX_MEMORY_NOTES = 15
TUTOR_MAX_TOKENS = 1500
HELPER_MAX_TOKENS = 600

# ---- course materials and guidelines (PRD §3.2-3.3; caps are build defaults) ---------
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_FILES_PER_UPLOAD = 20
MAX_FILES_PER_COURSE = 300
MAX_PAGES_PER_COURSE = 4000
GUIDELINE_MAX_CHARS = 4000
TAGGED_GUIDELINE_MAX_CHARS = 1000
MAX_TAGGED_GUIDELINES = 20
SMALL_GROUP_MIN = 5  # dashboard hides breakdowns for fewer students than this

# ---- deployment / security -------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()          # Postgres (Supabase) in prod; SQLite if empty
PRODUCTION = os.getenv("ENV", "").lower() == "production"
SECRET_KEY = os.getenv("SECRET_KEY", "")                       # signs local session tokens and file links
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
APP_URL = os.getenv("APP_URL", "").strip().rstrip("/") or (ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "http://localhost:5173")
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", str(7 * 24 * 3600)))
FILE_TOKEN_TTL_SECONDS = 3600
GLOBAL_DAILY_LIMIT = int(os.getenv("GLOBAL_DAILY_LIMIT", "600"))  # questions, all courses, rolling 24h (cost backstop)

# Supabase: Storage holds course files in production; Auth handles sign-up and login.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()   # server-side only (Storage)
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()         # public by design; handed to the browser
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "").strip()     # only for legacy HS256 tokens
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "course-pdfs")
AUTH_PROVIDER = (os.getenv("AUTH_PROVIDER", "").strip().lower()
                 or ("supabase" if SUPABASE_URL and SUPABASE_ANON_KEY else "local"))

# Stripe Checkout, test mode only in v1 (PRD §2.3). Without keys a built-in test checkout is used (dev only).
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()


def billing_mode() -> str:
    return "stripe" if STRIPE_SECRET_KEY else "mock"


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
        problems.append("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set (file storage)")
    if AUTH_PROVIDER != "supabase" or not SUPABASE_ANON_KEY:
        problems.append("AUTH_PROVIDER must be 'supabase' with SUPABASE_ANON_KEY set (local accounts are for development)")
    if not (STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET):
        problems.append("STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET must be set (the test checkout is for development)")
    elif not STRIPE_SECRET_KEY.startswith(("sk_test_", "rk_test_")):
        problems.append("STRIPE_SECRET_KEY must be a test-mode key: v1 takes sandbox payments only")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
