#!/usr/bin/env python3
"""Cross-profile status collector for Hermes Agent.

Scans ~/.hermes/profiles/ to find all profiles, determines their status
(active/idle/stopped), and writes results to:
  - ~/.hermes/cross_profile_status.json
  - ~/.hermes/cross_profile_status.js (for dashboard consumption)
"""

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

HERMES_DIR = Path.home() / ".hermes"
PROFILES_DIR = HERMES_DIR / "profiles"
OUTPUT_JSON = HERMES_DIR / "cross_profile_status.json"
OUTPUT_JS = HERMES_DIR / "cross_profile_status.js"
# Also write JS next to the dashboard for file:// compatibility
SCRIPT_DIR = Path(__file__).parent
OUTPUT_JS_LOCAL = SCRIPT_DIR / "dashboard_data.js"
RECIPE_DIR = Path.home() / "Desktop" / "配方"

ACTIVE_THRESHOLD_MINS = 5


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def now_dt() -> datetime.datetime:
    return datetime.datetime.now()


def find_all_gateways() -> list:
    """Find all hermes gateway processes and their profile associations."""
    result = subprocess.run(["ps", "-eo", "pid,etime,args"], capture_output=True, text=True, timeout=10)
    gateways = []
    for line in result.stdout.splitlines():
        if "hermes" not in line or "gateway" not in line or "grep" in line:
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue

        # Verify PID is still alive
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, OSError):
            continue  # Stale entry, skip

        # Parse elapsed time to filter out transient processes
        etime_str = parts[1]
        try:
            # Format can be: MM:SS, HH:MM:SS, D-HH:MM:SS
            etime_secs = 0
            if "-" in etime_str:
                days, rest = etime_str.split("-")
                etime_secs += int(days) * 86400
                etime_str = rest
            components = list(map(int, etime_str.split(":")))
            if len(components) == 3:
                etime_secs += components[0] * 3600 + components[1] * 60 + components[2]
            elif len(components) == 2:
                etime_secs += components[0] * 60 + components[1]
            if etime_secs < 30:
                continue  # Too young, likely transient
        except (ValueError, IndexError):
            pass  # Can't parse time, include it

        # Extract the command (everything after pid and etime)
        cmd = " ".join(parts[2:])

        # Check if --profile is specified
        if "--profile" in cmd:
            tokens = cmd.split()
            for i, tok in enumerate(tokens):
                if tok == "--profile" and i + 1 < len(tokens):
                    profile_name = tokens[i + 1]
                    gateways.append({"pid": pid, "profile": profile_name})
                    break
        else:
            gateways.append({"pid": pid, "profile": None})
    return gateways


def find_gateway_profile(profile_name: str, all_gateways: list) -> dict:
    """Check if a gateway process for the given profile is running."""
    # First, look for explicit --profile match
    for gw in all_gateways:
        if gw["profile"] == profile_name:
            return {"running": True, "pid": gw["pid"]}

    # Check gateway.pid file
    pid_file = PROFILES_DIR / profile_name / "gateway.pid"
    if pid_file.exists():
        try:
            raw = pid_file.read_text().strip()
            data = json.loads(raw)
            pid = data.get("pid")
            # Verify PID is still alive
            os.kill(pid, 0)
            return {"running": True, "pid": pid}
        except (json.JSONDecodeError, KeyError, ProcessLookupError, OSError, ValueError):
            pass

    return {"running": False, "pid": None}


def assign_unassigned_gateways(profiles_data: list, all_gateways: list) -> list:
    """Assign unassigned gateways (no --profile) to profiles that need them."""
    unassigned = [gw for gw in all_gateways if gw["profile"] is None]
    if not unassigned:
        return profiles_data

    # Find profiles that are "stopped" but might actually have the unassigned gateway
    stopped_profiles = [p for p in profiles_data if p["status"] == "stopped"]

    # Assign unassigned gateways to stopped profiles with activity indicators
    for gw in unassigned:
        # Find the best candidate: profile with most recent activity among stopped ones
        best_candidate = None
        best_activity = None
        for p in stopped_profiles:
            # Prefer profiles with session data or other activity
            activity = p.get("details", {}).get("session_last")
            if activity and (best_activity is None or activity > best_activity):
                best_candidate = p
                best_activity = activity

        # If no activity-based match, assign to first stopped profile
        if best_candidate is None and stopped_profiles:
            best_candidate = stopped_profiles[0]

        if best_candidate:
            best_candidate["status"] = "idle"  # Gateway up but unknown activity
            best_candidate["gateway_pid"] = gw["pid"]
            best_candidate["details"]["unassigned_gateway"] = True
            stopped_profiles = [p for p in stopped_profiles if p["name"] != best_candidate["name"]]

    return profiles_data


def check_session_activity(profile_name: str) -> dict:
    """Check sessions directory for most recent activity."""
    sessions_dir = PROFILES_DIR / profile_name / "sessions"
    if not sessions_dir.exists():
        return {"last_activity": None, "files_checked": 0}

    newest_mtime = None
    newest_file = None
    count = 0
    for f in sessions_dir.iterdir():
        if f.is_file():
            count += 1
            mtime = f.stat().st_mtime
            if newest_mtime is None or mtime > newest_mtime:
                newest_mtime = mtime
                newest_file = str(f)

    if newest_mtime:
        last_dt = datetime.datetime.fromtimestamp(newest_mtime)
        return {
            "last_activity": last_dt.isoformat(timespec="seconds"),
            "last_file": newest_file,
            "files_checked": count,
            "age_minutes": (now_dt() - last_dt).total_seconds() / 60,
        }
    return {"last_activity": None, "files_checked": count}


def check_recipe_outputs(profile_name: str) -> list:
    """Check ~/Desktop/配方/ subdirs for recent outputs associated with profile."""
    if not RECIPE_DIR.exists():
        return []

    # Map profile names to recipe subdirs
    profile_to_recipe = {
        "painpoint-miner": ["mined"],
        "agent-assembler": ["recipes", "autocraft"],
        "bbb-consultant": [],
        "test-runner": [],
        "sandbox": [],
    }

    subdirs = profile_to_recipe.get(profile_name, [])
    recent = []
    for subdir_name in subdirs:
        subdir = RECIPE_DIR / subdir_name
        if not subdir.exists():
            continue
        for f in subdir.iterdir():
            if f.is_file():
                mtime = f.stat().st_mtime
                age_mins = (now_dt() - datetime.datetime.fromtimestamp(mtime)).total_seconds() / 60
                if age_mins < ACTIVE_THRESHOLD_MINS * 6:  # Extended window for outputs
                    recent.append({
                        "file": str(f),
                        "age_minutes": round(age_mins, 1),
                    })
    return recent


def check_cron_activity(profile_name: str) -> dict:
    """Check cron/jobs.json for last_run timestamps."""
    cron_file = PROFILES_DIR / profile_name / "cron" / "jobs.json"
    if not cron_file.exists():
        return {"jobs": [], "last_run": None}

    try:
        data = json.loads(cron_file.read_text())
        jobs = data if isinstance(data, list) else data.get("jobs", [])
        last_run = None
        job_info = []
        for job in jobs:
            lr = job.get("last_run")
            job_info.append({"id": job.get("id", "?"), "last_run": lr})
            if lr:
                if last_run is None or lr > last_run:
                    last_run = lr
        return {"jobs": job_info, "last_run": last_run}
    except (json.JSONDecodeError, Exception):
        return {"jobs": [], "last_run": None}


def infer_status(gateway: dict, session: dict, outputs: list, cron: dict) -> str:
    """Determine profile status from collected data."""
    if not gateway["running"]:
        return "stopped"

    # Gateway is up - check for recent activity
    if session["last_activity"]:
        age = session.get("age_minutes", 999)
        if age < ACTIVE_THRESHOLD_MINS:
            return "active"

    # Check recipe outputs for recent activity
    for out in outputs:
        if out.get("age_minutes", 999) < ACTIVE_THRESHOLD_MINS:
            return "active"

    return "idle"


def collect_profile(profile_name: str, all_gateways: list) -> dict:
    """Collect all status data for a single profile."""
    gateway = find_gateway_profile(profile_name, all_gateways)
    session = check_session_activity(profile_name)
    outputs = check_recipe_outputs(profile_name)
    cron = check_cron_activity(profile_name)

    status = infer_status(gateway, session, outputs, cron)

    # Determine last activity timestamp (most recent across all sources)
    timestamps = []
    if session["last_activity"]:
        timestamps.append(session["last_activity"])
    if cron["last_run"]:
        timestamps.append(cron["last_run"])

    last_activity = max(timestamps) if timestamps else None

    return {
        "name": profile_name,
        "status": status,
        "gateway_pid": gateway.get("pid"),
        "last_activity": last_activity,
        "current_task": None,  # Could be enhanced later from session state
        "recent_outputs": outputs[:5],  # Limit to 5
        "details": {
            "session_last": session.get("last_activity"),
            "session_file": session.get("last_file"),
            "cron_last_run": cron.get("last_run"),
            "job_count": len(cron.get("jobs", [])),
        },
    }


def main():
    if not PROFILES_DIR.exists():
        print(f"ERROR: Profiles directory not found: {PROFILES_DIR}", file=sys.stderr)
        sys.exit(1)

    profiles = sorted([d.name for d in PROFILES_DIR.iterdir() if d.is_dir()])
    if not profiles:
        print("WARNING: No profiles found.", file=sys.stderr)

    print(f"Collecting status for {len(profiles)} profiles: {', '.join(profiles)}")

    # Discover all gateway processes once
    all_gateways = find_all_gateways()
    print(f"Found {len(all_gateways)} gateway process(es)")

    results = []
    for pname in profiles:
        try:
            profile_data = collect_profile(pname, all_gateways)
            results.append(profile_data)
            print(f"  {pname}: {profile_data['status']} (PID: {profile_data['gateway_pid']})")
        except Exception as e:
            print(f"  {pname}: ERROR - {e}", file=sys.stderr)
            results.append({
                "name": pname,
                "status": "error",
                "gateway_pid": None,
                "last_activity": None,
                "current_task": None,
                "recent_outputs": [],
                "error": str(e),
            })

    # Assign unassigned gateways to profiles that need them
    results = assign_unassigned_gateways(results, all_gateways)

    output = {
        "timestamp": now_iso(),
        "profiles": results,
    }

    # Write JSON
    OUTPUT_JSON.write_text(json.dumps(output, indent=2))
    print(f"\nJSON written to: {OUTPUT_JSON}")

    # Write JS for dashboard (file:// protocol compatible)
    js_content = f"window.dashboardData = {json.dumps(output, indent=2)};"
    OUTPUT_JS.write_text(js_content)
    print(f"JS written to: {OUTPUT_JS}")

    # Also write JS next to the dashboard for file:// compatibility
    OUTPUT_JS_LOCAL.write_text(js_content)
    print(f"JS (local) written to: {OUTPUT_JS_LOCAL}")

    # Summary
    status_counts = {}
    for p in results:
        s = p["status"]
        status_counts[s] = status_counts.get(s, 0) + 1
    print(f"\nSummary: {dict(status_counts)}")


if __name__ == "__main__":
    main()
