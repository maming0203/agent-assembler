"""Shared configuration and paths for the Gateway package."""
import os

IS_CLOUD = os.path.exists("/data/jit")

if IS_CLOUD:
    RECIPE_BASE = "/data/jit/recipes"
    SKILL_BASE = "/data/jit/skills"
    AUTO_DIR = "/data/jit/recipes/AutoCreated"
else:
    RECIPE_BASE = os.path.expanduser("~/Desktop/配方")
    SKILL_BASE = os.path.expanduser("~/.hermes/skills")
    AUTO_DIR = os.path.expanduser("~/Desktop/配方/AutoCreated")

SKILL_AUTO_DIR = os.path.join(AUTO_DIR, "Skills")
os.makedirs(AUTO_DIR, exist_ok=True)
os.makedirs(SKILL_AUTO_DIR, exist_ok=True)

BASE_DIR = os.environ.get("ASSEMBLER_BASE_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = BASE_DIR
INGESTOR_SCRIPT = os.path.join(PROJECT_ROOT, "api_gateway", "universal_ingestor.py")
DISPATCHER_SCRIPT = os.environ.get("ASSEMBLER_DISPATCHER", os.path.join(BASE_DIR, "code", "dispatcher.py"))
MANIFESTS_DIR = os.environ.get("ASSEMBLER_MANIFESTS", os.path.join(BASE_DIR, "code", "manifests"))
ROUTING_SCHEMA_PATH = os.path.join(PROJECT_ROOT, "api_gateway", "routing_schema.json")


UPLOAD_DIR = os.path.expanduser("~/Desktop/agent-assembler/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_DIR = os.path.expanduser("~/.agent-assembler")
os.makedirs(DB_DIR, exist_ok=True)
DB_FILE = os.path.join(DB_DIR, "user_db.json")
USAGE_FILE = os.path.join(DB_DIR, "user_usage.json")

AUTOCRAFT_REF_DIR = os.path.join(PROJECT_ROOT, "api_gateway")
RECIPE_SCHEMA_PATH = os.path.join(PROJECT_ROOT, "api_gateway", "recipe_schema.json")

SCRIPT_DIRS = [
    os.path.join(PROJECT_ROOT, "code", "scripts"),
]
