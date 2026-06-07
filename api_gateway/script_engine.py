"""Script Execution Engine — path safety, execution, arg extraction."""
import json
import os
import re
import subprocess
from typing import Tuple

SCRIPT_DIRS = [
    os.path.expanduser("~/.hermes/recipes/scripts"),
    "/data/jit/recipes/scripts",
]


def _validate_script_path(script_path: str) -> Tuple[bool, str]:
    """Validate that a script path is safe to execute."""
    if not script_path:
        return False, "Empty script path"
    if ".." in script_path:
        return False, f"Path traversal not allowed: {script_path}"
    dangerous = ["/bin/", "/sbin/", "/usr/bin/", "/usr/sbin/", "/etc/", "/dev/", "/proc/", "/sys/"]
    for dp in dangerous:
        if script_path.startswith(dp):
            return False, f"Dangerous path rejected: {script_path}"
    if os.path.isabs(script_path):
        if not script_path.endswith(".py"):
            return False, f"Script must be a .py file: {script_path}"
        if os.path.exists(script_path):
            return True, script_path
        return False, f"Script file not found: {script_path}"
    for base in SCRIPT_DIRS:
        candidate = os.path.normpath(os.path.join(base, script_path))
        if not candidate.startswith(base):
            continue
        if os.path.exists(candidate):
            return True, candidate
    candidate = os.path.normpath(os.path.abspath(script_path))
    if os.path.exists(candidate) and candidate.endswith(".py"):
        return True, candidate
    return False, f"Script file not found in any known directory: {script_path}"


def _run_script(script_path: str, args: dict) -> Tuple[bool, str]:
    """Execute a Python script with the given arguments."""
    is_safe, resolved = _validate_script_path(script_path)
    if not is_safe:
        return False, f"[Script Error] {resolved}"
    print(f"[Script Engine] Executing: {resolved} with args: {json.dumps(args, ensure_ascii=False)[:200]}")
    try:
        result = subprocess.run(
            ["python3", resolved, json.dumps(args, ensure_ascii=False)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            print(f"[Script Engine] Success: {output[:200]}...")
            return True, output
        else:
            err = result.stderr.strip()[:500]
            print(f"[Script Engine] Error (rc={result.returncode}): {err}")
            return False, f"[Script Error] {err}"
    except subprocess.TimeoutExpired:
        return False, "[Script Error] Execution timed out (60s)"
    except FileNotFoundError:
        return False, "[Script Error] python3 not found on this system"
    except Exception as e:
        return False, f"[Script Error] {str(e)}"


def _extract_script_args(recipe: dict, query: str) -> dict:
    """Extract script arguments from recipe definition and user query."""
    args = recipe.get("script_args", {}).copy() if isinstance(recipe.get("script_args"), dict) else {}
    ec = recipe.get("engine_config", {})
    if isinstance(ec, dict) and "script_args" in ec:
        args.update(ec["script_args"])
    for match in re.findall(r"(\w+)\s*[=:]\s*([^\s,;]+)", query):
        key, val = match
        args[key] = val
    args["query"] = query
    return args
