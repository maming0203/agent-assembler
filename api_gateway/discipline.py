"""P6 — Runtime Discipline Layer (运行时纪律层)

Enforcement middleware between Gateway routing and Agent execution.
Not advice. Rules. Violation = rejection.

Protocols:
  1. Recipe-First      — must retrieve recipes before assembling context
  2. Container Wall    — file writes must use vault_write.py
  3. Skill Hardening   — ≤4KB per skill, explicit-only loading, no full dump
  4. Routing Enforce   — if recipe specifies routing, forward directly
  5. Audit Separation  — skill modification ≠ evaluation
  6. Inline Evolution  — dynamic skill split on-the-fly when >4KB
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

# ===== Constants =====
SKILL_SIZE_LIMIT = 4096  # 4KB hard limit
HERMES_RECIPES = os.path.expanduser("~/.hermes/recipes")
VAULT_WRITE_SCRIPT = os.path.expanduser("~/.openclaw/workspace/scripts/vault_write.py")

# ===== Data Structures =====

@dataclass
class DisciplineCheck:
    """Result of discipline validation."""
    passed: bool
    violations: list[str] = field(default_factory=list)
    enforced_recipe: Optional[dict] = None
    enforced_skills: list[str] = field(default_factory=list)
    routing_target: Optional[str] = None
    system_prompt_injection: str = ""

    def fail(self, reason: str):
        self.violations.append(reason)
        self.passed = False


# ===== Protocol 1: Recipe-First =====

def retrieve_hermes_recipes(query: str) -> Optional[dict]:
    """Retrieve recipe from ~/.hermes/recipes/ before assembling context.
    
    If query matches trigger_keywords of any recipe, return it.
    Caller MUST use this recipe's skill list — no ad-hoc assembly.
    """
    if not os.path.exists(HERMES_RECIPES):
        return None
    
    for root, dirs, files in os.walk(HERMES_RECIPES):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if not f.endswith(".json"):
                continue
            try:
                with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                    recipe = json.load(fh)
                keywords = recipe.get("trigger_keywords", recipe.get("triggers", []))
                query_lower = query.lower()
                if any(kw.lower() in query_lower for kw in keywords):
                    return recipe
            except Exception:
                continue
    return None


# ===== Protocol 2: Container Wall Hardening =====

def validate_container_wall(recipe: dict) -> DisciplineCheck:
    """Enforce: all file writes must use vault_write.py.
    
    If recipe involves file writing, inject mandatory prompt.
    Violation = container breach → rollback + re-execute.
    """
    check = DisciplineCheck(passed=True)
    
    # Check if recipe involves document/file operations
    notes = (recipe.get("notes", "") + " " + recipe.get("description", "")).lower()
    file_keywords = ["写文件", "写文档", "write file", "write doc", "保存文件", "生成报告",
                     "output file", "生成文档", "落盘", "写入"]
    involves_file_write = any(kw in notes for kw in file_keywords)
    
    if involves_file_write:
        vault_exists = os.path.exists(VAULT_WRITE_SCRIPT)
        check.system_prompt_injection = (
            "\n\n⚠️ CONTAINER WALL ENFORCED ⚠️\n"
            f"All file writes MUST use vault_write.py script.\n"
            f"DO NOT use cat >, echo >, or direct file operations.\n"
            f"Script path: {VAULT_WRITE_SCRIPT}\n"
            f"Status: {'✅ Available' if vault_exists else '❌ NOT FOUND - escalation required'}\n"
        )
        if not vault_exists:
            check.fail(f"vault_write.py not found at {VAULT_WRITE_SCRIPT}")
    
    return check


# ===== Protocol 3: Skill Hardening =====

def validate_skill_hardening(skills: list[str], skill_dir: str) -> DisciplineCheck:
    """Enforce: each skill ≤4KB, explicit-only loading, no full dump.
    
    Violation = skill too large → reject, must split first.
    """
    check = DisciplineCheck(passed=True)
    check.enforced_skills = skills
    
    for skill_name in skills:
        if not isinstance(skill_name, str):
            continue
        
        # Look for skill file
        skill_path = None
        for root, dirs, files in os.walk(skill_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if skill_name.lower() in f.lower() or f.lower() in skill_name.lower():
                    skill_path = os.path.join(root, f)
                    break
            if skill_path:
                break
        
        if not skill_path:
            continue  # Skill not found, will fail at load time, not discipline
        
        # Size check
        try:
            size = os.path.getsize(skill_path)
            if size > SKILL_SIZE_LIMIT:
                check.fail(
                    f"Skill '{skill_name}' exceeds 4KB limit ({size} bytes). "
                    f"Must split into atomic skills before loading."
                )
        except OSError:
            pass
    
    return check


# ===== Protocol 4: Routing Enforcement =====

def enforce_routing(recipe: dict, current_agent: str = "") -> DisciplineCheck:
    """Enforce: if recipe specifies routing, forward directly.
    
    Never handle locally. Never bypass routing.
    """
    check = DisciplineCheck(passed=True)
    
    routing = recipe.get("routing", "")
    if isinstance(routing, dict):
        routing = routing.get("agent_id", routing.get("primary_agent", ""))
    
    if routing and routing.lower() not in ("", "general", "default"):
        check.routing_target = routing
        # If current agent is not the target, must forward
        if current_agent and routing.lower() != current_agent.lower():
            check.system_prompt_injection += (
                f"\n\n⚠️ ROUTING ENFORCED ⚠️\n"
                f"This task routes to: {routing}\n"
                f"DO NOT handle locally. Forward immediately.\n"
            )
    
    return check


# ===== Protocol 5: Audit Separation =====

def audit_separation_required(recipe: dict) -> bool:
    """Return True if this recipe's output needs independent audit.
    
    Rule: skill modifications require separate audit session.
    AI self-assessment accuracy is only 46.4% (Microsoft study).
    """
    notes = (recipe.get("notes", "") + " " + recipe.get("description", "")).lower()
    audit_keywords = ["skill", "修改", "优化", "update skill", "modify", "split", "拆分"]
    return any(kw in notes for kw in audit_keywords)


# ===== Protocol 6: Inline Evolution =====

def check_skill_size_inline(skill_path: str) -> dict:
    """Check skill size at runtime. If >4KB, return split suggestion.
    
    This is a soft check — warns but doesn't block (split requires human action).
    """
    if not os.path.exists(skill_path):
        return {"ok": False, "error": "Skill file not found"}
    
    size = os.path.getsize(skill_path)
    if size <= SKILL_SIZE_LIMIT:
        return {"ok": True, "size": size}
    
    # Read content to suggest split points
    with open(skill_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find natural split points (## headers, ---, or ## sections)
    split_points = []
    for match in ['## ', '---', '### ']:
        positions = [i for i in range(len(content)) if content.startswith(match, i)]
        if positions:
            split_points = positions
            break
    
    return {
        "ok": False,
        "size": size,
        "over_by": size - SKILL_SIZE_LIMIT,
        "suggested_splits": len(split_points),
    }


# ===== Master Gate: All Protocols =====

def run_discipline_gate(
    query: str,
    skill_dir: str,
    current_agent: str = "",
    recipe: Optional[dict] = None,
) -> DisciplineCheck:
    """Master gate: run all 5 protocols before execution.
    
    Returns DisciplineCheck with violations (if any) and system prompt injections.
    
    Usage:
        check = run_discipline_gate(query, skill_dir, recipe=matched_recipe)
        if not check.passed:
            return {"status": "discipline_violation", "violations": check.violations}
        # Proceed with execution, inject check.system_prompt_injection
    """
    result = DisciplineCheck(passed=True)
    
    # Protocol 1: Recipe-First (if no recipe provided)
    if not recipe:
        recipe = retrieve_hermes_recipes(query)
    if recipe:
        result.enforced_recipe = recipe
    
    # Protocol 2: Container Wall
    if recipe:
        wall = validate_container_wall(recipe)
        if not wall.passed:
            result.fail("; ".join(wall.violations))
        result.system_prompt_injection += wall.system_prompt_injection
    
    # Protocol 3: Skill Hardening
    if recipe:
        skills = recipe.get("skills", [])
        if isinstance(skills, list):
            skill_names = [s if isinstance(s, str) else s.get("name", "") for s in skills]
            skill_names = [s for s in skill_names if s]
            hardening = validate_skill_hardening(skill_names, skill_dir)
            if not hardening.passed:
                result.fail("; ".join(hardening.violations))
    
    # Protocol 4: Routing Enforcement
    if recipe:
        routing = enforce_routing(recipe, current_agent)
        if routing.routing_target:
            result.routing_target = routing.routing_target
        result.system_prompt_injection += routing.system_prompt_injection
    
    return result


# ===== Public API for Gateway =====

def discipline_enforce_prompt(
    query: str,
    skill_dir: str,
    current_agent: str = "",
    recipe: Optional[dict] = None,
) -> dict:
    """Convenience function: returns discipline check + prompt injection for Gateway.
    
    Returns dict with:
    - passed: bool
    - violations: list[str]
    - prompt_injection: str (append to agent query)
    - routing_override: str or None
    - recipe_used: dict or None
    """
    check = run_discipline_gate(query, skill_dir, current_agent, recipe)
    
    return {
        "passed": check.passed,
        "violations": check.violations,
        "prompt_injection": check.system_prompt_injection,
        "routing_override": check.routing_target,
        "recipe_used": check.enforced_recipe,
    }
