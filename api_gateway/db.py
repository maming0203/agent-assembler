"""DB helpers — user DB, usage tracking, recipe matching, skill loading."""
import json
import os
import time

from .config import DB_FILE, USAGE_FILE, RECIPE_BASE, SKILL_BASE, SKILL_AUTO_DIR, IS_CLOUD

if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w", encoding="utf-8") as fh:
        fh.write("{}")
if not os.path.exists(USAGE_FILE):
    with open(USAGE_FILE, "w", encoding="utf-8") as fh:
        fh.write("{}")


def load_json(f):
    try:
        with open(f, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_json(f, data):
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def is_premium(r):
    return r.get("_source_premium", False)


def paywall_response(msg):
    return {"status": "paywall", "message": msg, "price": "9.9", "title": "升级 Pro 解锁无限配方"}


def get_user_id_by_key(key):
    db = load_json(DB_FILE)
    for uid, info in db.items():
        if isinstance(info, str) and info == key:
            return uid
        if isinstance(info, dict) and info.get("api_key") == key:
            return uid
    return None


def find_recipe(query):
    base = RECIPE_BASE
    if not os.path.exists(base):
        return None
    for root, _, files in os.walk(base):
        if "Premium_Assets" in root:
            continue
        for f in files:
            if f.endswith(".json"):
                try:
                    with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                        d = json.load(fh)
                    for kw in d.get("trigger_keywords", []):
                        if len(kw) < 4:  # 跳过过于宽泛的短关键词
                            continue
                        if kw in query:
                            d["_source_premium"] = False
                            d["filename"] = f.replace(".json", "")
                            return d
                except Exception:
                    pass
    for root, _, files in os.walk(base):
        if "Premium_Assets" not in root:
            continue
        for f in files:
            if f.endswith(".json"):
                try:
                    with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                        d = json.load(fh)
                    for kw in d.get("trigger_keywords", []):
                        if len(kw) < 4:  # 跳过过于宽泛的短关键词
                            continue
                        if kw in query:
                            d["_source_premium"] = True
                            d["filename"] = f.replace(".json", "")
                            return d
                except Exception:
                    pass
    return None


def find_skill_in_directory(base_dir, filename):
    if not os.path.exists(base_dir):
        return None
    for root, dirs, files in os.walk(base_dir):
        if "AutoCreated" in root and base_dir in root:
            continue
        if os.path.basename(root) == filename:
            skill_file = os.path.join(root, "SKILL.md")
            if os.path.exists(skill_file):
                return skill_file
        if f"{filename}.md" in files:
            return os.path.join(root, f"{filename}.md")
    return None


def load_skill(recipe):
    fn = recipe.get("filename", "unknown")
    skill_rel = recipe.get("skill", "")
    if IS_CLOUD and skill_rel:
        path = os.path.join(SKILL_BASE, f"{skill_rel}/SKILL.md")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return fh.read()
    auto_path = f"{SKILL_AUTO_DIR}/{fn}.md"
    if os.path.exists(auto_path):
        with open(auto_path, encoding="utf-8") as fh:
            return fh.read()
    found = find_skill_in_directory(SKILL_BASE, fn)
    if found:
        with open(found, encoding="utf-8") as fh:
            return fh.read()
    return "Provide expert advice based on general knowledge."


def check_usage(uid):
    usage = load_json(USAGE_FILE)
    today = time.strftime("%Y-%m-%d")
    val = usage.get(uid, {})
    if not isinstance(val, dict):
        return val if isinstance(val, int) else 0
    return val.get(today, 0)



def increment_usage(uid):
    usage = load_json(USAGE_FILE)
    today = time.strftime("%Y-%m-%d")
    val = usage.get(uid)
    if not isinstance(val, dict):
        # Migrate legacy int value to dict format
        old_count = val if isinstance(val, int) else 0
        usage[uid] = {today: old_count + 1}
    else:
        val[today] = val.get(today, 0) + 1
    save_json(USAGE_FILE, usage)
