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

INGESTOR_SCRIPT = os.path.expanduser("~/.hermes/recipes/scripts/universal_ingestor.py")
DISPATCHER_SCRIPT = os.path.expanduser("~/.openclaw/wiki/main/00-文档库/01-Projects/Agent-Assembler/code/dispatcher.py")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTING_SCHEMA_PATH = os.path.join(PROJECT_ROOT, "routing_schema.json")

MANIFESTS_DIR = os.path.expanduser("~/.openclaw/wiki/main/00-文档库/01-Projects/Agent-Assembler/code/manifests")

UPLOAD_DIR = os.path.expanduser("~/Desktop/agent-assembler/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_DIR = os.path.expanduser("~/.agent-assembler")
os.makedirs(DB_DIR, exist_ok=True)
DB_FILE = os.path.join(DB_DIR, "user_db.json")
USAGE_FILE = os.path.join(DB_DIR, "user_usage.json")

AUTOCRAFT_REF_DIR = os.path.join(PROJECT_ROOT, "autocraft", "references")
RECIPE_SCHEMA_PATH = os.path.join(AUTOCRAFT_REF_DIR, "recipe_schema.json")
RECIPE_TEMPLATE_PATH = os.path.join(AUTOCRAFT_REF_DIR, "recipe_template.py")

SCRIPT_DIRS = [
    os.path.expanduser("~/.hermes/recipes/scripts"),
    "/data/jit/recipes/scripts",
]
