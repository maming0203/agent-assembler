"""Workflow Engine — DAG-based workflow execution with serial/parallel/conditional/dataflow support."""
import json
import os
import time
import subprocess
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .config import IS_CLOUD, RECIPE_BASE
from .script_engine import _validate_script_path, _run_script

# ── Path configuration ──
if IS_CLOUD:
    WORKFLOW_DIR = "/data/jit/workflow/workflow-examples"
    RECIPE_SEARCH_DIRS = ["/data/jit/recipes", "/data/jit/recipes/AutoCreated"]
    SCRIPT_DIRS = ["/data/jit/scripts", "/data/jit/recipes/scripts"]
else:
    WORKFLOW_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "jit", "workflow", "workflow-examples"
    )
    RECIPE_SEARCH_DIRS = [
        os.path.expanduser("~/Desktop/配方"),
        os.path.expanduser("~/Desktop/配方/AutoCreated"),
    ]
    SCRIPT_DIRS = [
        os.path.expanduser("~/Desktop/agent-assembler/code/scripts"),
    ]
# Risk level normalization for condition evaluation
RISK_ORDER = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
RISK_ALIASES = {"high": "red", "medium": "orange", "low": "yellow", "safe": "green"}

def _normalize_risk(value):
    """Convert risk level string to numeric value for comparison."""
    if value is None:
        return None
    s = str(value).lower()
    if s in RISK_ORDER:
        return RISK_ORDER[s]
    if s in RISK_ALIASES:
        return RISK_ORDER[RISK_ALIASES[s]]
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def _cmp_risk(a, b, op):
    """Compare two values with risk-level awareness."""
    if a is None or b is None:
        return False
    na = _normalize_risk(a)
    nb = _normalize_risk(b)
    if na is not None and nb is not None:
        return op(na, nb)
    return False

# Operator handlers for condition evaluation with risk-level support
OPERATORS = {
    "gt": lambda a, b: _cmp_risk(a, b, lambda x, y: x > y),
    "lt": lambda a, b: _cmp_risk(a, b, lambda x, y: x < y),
    "gte": lambda a, b: _cmp_risk(a, b, lambda x, y: x >= y),
    "lte": lambda a, b: _cmp_risk(a, b, lambda x, y: x <= y),
    "eq": lambda a, b: _cmp_risk(a, b, lambda x, y: x == y),
    "ne": lambda a, b: _cmp_risk(a, b, lambda x, y: x != y),
    "contains": lambda a, b: a is not None and b is not None and str(b) in str(a),
    "in": lambda a, b: a is not None and b is not None and str(a) in str(b),
}

def _resolve_recipe(recipe_name: str) -> Optional[str]:
    """Resolve a recipe name to a script path by scanning recipe directories."""
    if not recipe_name:
        return None
    # If it's already a path
    if recipe_name.endswith(".py") and os.path.isabs(recipe_name):
        if os.path.exists(recipe_name):
            return recipe_name
        return None
    # Scan recipe directories
    for base in RECIPE_SEARCH_DIRS:
        if not os.path.exists(base):
            continue
        for root, _dirs, files in os.walk(base):
            for f in files:
                if f.endswith(".json"):
                    try:
                        with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                            data = json.load(fh)
                        name = data.get("name", "")
                        filename = data.get("filename", f.replace(".json", ""))
                        if name == recipe_name or filename == recipe_name:
                            # Found recipe, check for script_path
                            script = data.get("script_path") or data.get("script") or data.get("code")
                            if script:
                                # Validate the script path actually exists
                                if os.path.isabs(script):
                                    if os.path.exists(script):
                                        return script
                                else:
                                    # Try relative to recipe base and known script dirs
                                    for base in RECIPE_SEARCH_DIRS + SCRIPT_DIRS:
                                        candidate = os.path.join(base, script)
                                        if os.path.exists(candidate):
                                            return candidate
                                    # Script path declared but file not found — treat as LLM-only
                                    return f"__LLM_ONLY__:{recipe_name}"
                                return script
                            # No script — recipe is LLM-only, return special marker
                            return f"__LLM_ONLY__:{recipe_name}"
                    except Exception:
                        continue
    return None


def _run_script_json(recipe_name: str, args: dict) -> Tuple[bool, dict]:
    """Execute a recipe's script and return JSON result.
    
    Reuses script_engine._run_script for safe execution.
    For LLM-only recipes (no script), returns a placeholder result.
    """
    script_path = _resolve_recipe(recipe_name)
    if script_path is None:
        return False, {
            "error": f"Recipe '{recipe_name}' not found",
            "render_type": "error_card",
            "title": "配方未找到",
            "summary": f"未找到配方：{recipe_name}",
            "data": {},
        }

    # LLM-only recipe (no script)
    if script_path.startswith("__LLM_ONLY__:"):
        actual_name = script_path.split(":", 1)[1]
        return True, {
            "render_type": "text_card",
            "title": actual_name,
            "summary": f"配方 '{actual_name}' 已匹配（LLM模式）",
            "data": {"recipe": actual_name, "args": args},
            "actions": [],
        }

    # Use --json mode for passing structured arguments to the script
    try:
        json_input = json.dumps(args, ensure_ascii=False)
        process_result = subprocess.run(
            ["python3", script_path, "--json", json_input],
            capture_output=True, text=True, timeout=60,
        )
        success = process_result.returncode == 0
        output = process_result.stdout.strip() if success else process_result.stderr.strip()[:500]
        if not success:
            output = f"[Script Error] {output}"
    except subprocess.TimeoutExpired:
        success, output = False, "[Script Error] Execution timed out (60s)"
    except FileNotFoundError:
        success, output = False, "[Script Error] python3 not found"
    except Exception as e:
        success, output = False, f"[Script Error] {str(e)}"
    if success:
        # Try to parse JSON output
        try:
            result = json.loads(output)
            return True, result
        except (json.JSONDecodeError, TypeError):
            return True, {
                "render_type": "text_card",
                "title": recipe_name,
                "summary": output[:500],
                "data": {"raw_output": output},
                "actions": [],
            }
    else:
        return False, {
            "error": output,
            "render_type": "error_card",
            "title": recipe_name,
            "summary": f"执行失败：{output[:200]}",
            "data": {},
        }


def _resolve_field(field: str, context: dict) -> Any:
    """Resolve a dotted field path from context, e.g. 'user.dailyRevenue' or 'step_1.score'."""
    parts = field.split(".")
    current = context
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if current is None:
            return None
    return current


def topological_sort(steps: list) -> List[list]:
    """Topological sort of workflow steps, returning execution layers.
    
    Steps in the same layer can run in parallel.
    Returns a list of lists, where each inner list is a layer of steps.
    """
    # Build adjacency list and in-degree count
    step_map = {s["id"]: s for s in steps}
    in_degree = {s["id"]: 0 for s in steps}
    dependents = defaultdict(list)  # step_id -> list of steps that depend on it

    for step in steps:
        for dep in step.get("depends_on", []):
            if dep in step_map:
                in_degree[step["id"]] += 1
                dependents[dep].append(step["id"])

    # Kahn's algorithm with layering
    layers = []
    current_layer = [sid for sid, deg in in_degree.items() if deg == 0]

    while current_layer:
        layers.append(current_layer)
        next_layer = []
        for sid in current_layer:
            for dependent in dependents[sid]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_layer.append(dependent)
        current_layer = next_layer

    # Detect cycles: if not all steps are in layers
    if sum(len(l) for l in layers) != len(steps):
        # Fallback: just return all steps as single layer
        # (cycle detection should ideally raise an error)
        return [steps]

    return layers


class WorkflowEngine:
    """DAG-based workflow execution engine."""

    def __init__(self, workflow_dir: str = None):
        self.workflow_dir = workflow_dir or WORKFLOW_DIR
        self._workflow_cache: Dict[str, dict] = {}

    def load_workflow(self, workflow_name: str) -> Optional[dict]:
        """Load a workflow definition by name.
        
        Scans the workflow-examples directory for a matching JSON file.
        Matches by 'name' field or filename.
        """
        # Check cache
        if workflow_name in self._workflow_cache:
            return self._workflow_cache[workflow_name]

        if not os.path.exists(self.workflow_dir):
            return None

        for root, _dirs, files in os.walk(self.workflow_dir):
            for f in files:
                if not f.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    name = data.get("name", "")
                    filename = f.replace(".json", "")
                    if name == workflow_name or filename == workflow_name:
                        self._workflow_cache[workflow_name] = data
                        return data
                except Exception:
                    continue

        return None

    def list_workflows(self) -> List[dict]:
        """List all available workflows."""
        workflows = []
        if not os.path.exists(self.workflow_dir):
            return workflows

        for root, _dirs, files in os.walk(self.workflow_dir):
            for f in files:
                if not f.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    workflows.append({
                        "name": data.get("name", f.replace(".json", "")),
                        "version": data.get("version", "unknown"),
                        "description": data.get("description", ""),
                        "step_count": len(data.get("steps", [])),
                        "file": f,
                    })
                except Exception:
                    continue

        return workflows

    def _check_condition(self, condition: dict, context: dict) -> bool:
        """Evaluate a condition against the execution context.
        
        Supports operators: gt, lt, eq, ne, contains, in, gte, lte
        """
        field = condition.get("field", "")
        operator = condition.get("operator", "eq")
        value = condition.get("value")

        actual_value = _resolve_field(field, context)
        handler = OPERATORS.get(operator)
        if handler is None:
            print(f"[Workflow] Unknown operator: {operator}")
            return False

        try:
            return handler(actual_value, value)
        except (TypeError, ValueError) as e:
            print(f"[Workflow] Condition eval error: {e}")
            return False

    def _execute_step(self, step: dict, inputs: dict, context: dict) -> dict:
        """Execute a single workflow step."""
        recipe = step.get("recipe", "")
        step_id = step["id"]
        max_retries = step.get("max_retries", 0)
        on_failure = step.get("on_failure", "abort")
        fallback = step.get("fallback")

        attempts = 0
        last_error = None

        while attempts <= max_retries:
            if attempts > 0:
                print(f"[Workflow] Retry {attempts}/{max_retries} for step '{step_id}'")
                time.sleep(0.5)

            success, result = _run_script_json(recipe, inputs)

            if success:
                return {
                    "step_id": step_id,
                    "status": "success",
                    "data": result,
                    "attempts": attempts + 1,
                }

            last_error = result
            attempts += 1

        # All attempts failed
        if on_failure == "retry" and attempts > max_retries:
            return {
                "step_id": step_id,
                "status": "failed",
                "error": last_error,
                "attempts": attempts,
                "on_failure": on_failure,
            }

        if on_failure == "skip":
            return {
                "step_id": step_id,
                "status": "skipped",
                "reason": "step_failed",
                "error": last_error,
            }

        if on_failure == "fallback" and fallback:
            print(f"[Workflow] Using fallback '{fallback}' for step '{step_id}'")
            success, result = _run_script_json(fallback, inputs)
            if success:
                return {
                    "step_id": step_id,
                    "status": "fallback_success",
                    "data": result,
                    "original_error": last_error,
                }
            return {
                "step_id": step_id,
                "status": "fallback_failed",
                "error": result,
                "original_error": last_error,
            }

        # Default: abort
        return {
            "step_id": step_id,
            "status": "failed",
            "error": last_error,
            "on_failure": on_failure,
            "abort_workflow": True,
        }

    def execute(self, workflow_name: str, user_inputs: dict = None) -> dict:
        """Execute a workflow with the given user inputs.
        
        Returns structured execution results.
        """
        workflow = self.load_workflow(workflow_name)
        if not workflow:
            return {
                "status": "error",
                "message": f"Workflow '{workflow_name}' not found",
                "workflow": workflow_name,
            }

        steps = workflow.get("steps", [])
        if not steps:
            return {
                "status": "error",
                "message": "Workflow has no steps",
                "workflow": workflow_name,
            }

        user_inputs = user_inputs or {}
        step_results: Dict[str, dict] = {}
        context = {"user": user_inputs}
        execution_log = []
        completed_steps = []
        warnings = []
        aborted = False
        abort_reason = None

        # Topological sort into execution layers
        layers = topological_sort(steps)
        step_map = {s["id"]: s for s in steps}

        for layer_idx, layer in enumerate(layers):
            if aborted:
                break

            # Check parallel_group — group steps that share a parallel_group
            parallel_groups: Dict[str, list] = defaultdict(list)
            standalone_steps = []

            for step_id in layer:
                step = step_map[step_id]
                group = step.get("parallel_group")
                if group:
                    parallel_groups[group].append(step)
                else:
                    standalone_steps.append(step)

            # Execute standalone steps sequentially
            for step in standalone_steps:
                if aborted:
                    break
                result = self._execute_single_step(step, step_results, context, user_inputs)
                step_results[step["id"]] = result
                execution_log.append({
                    "step_id": step["id"],
                    "layer": layer_idx,
                    "result": result,
                })
                # P2a: consistency check after successful step
                if result.get("status") in ("success", "fallback_success"):
                    completed_steps.append(step["id"])
                    consistency = self._check_consistency(workflow, context, completed_steps)
                    if not consistency["pass"]:
                        print(f"[Workflow Consistency] Failed: {consistency['reason']}")
                        if consistency["action"] == "abort":
                            aborted = True
                            abort_reason = f"Consistency check '{consistency['rule']}' failed: {consistency['reason']}"
                            result["consistency_abort"] = True
                            break
                        elif consistency["action"] == "warn":
                            warnings.append(consistency)
                if result.get("abort_workflow"):
                    aborted = True
                    abort_reason = f"Step '{step['id']}' failed with abort policy"
                    break

            # Execute parallel groups
            for group_name, group_steps in parallel_groups.items():
                if aborted:
                    break
                print(f"[Workflow] Executing parallel group '{group_name}' with {len(group_steps)} steps")
                for step in group_steps:
                    result = self._execute_single_step(step, step_results, context, user_inputs)
                    step_results[step["id"]] = result
                    execution_log.append({
                        "step_id": step["id"],
                        "layer": layer_idx,
                        "parallel_group": group_name,
                        "result": result,
                    })
                    # P2a: consistency check after successful step
                    if result.get("status") in ("success", "fallback_success"):
                        completed_steps.append(step["id"])
                        consistency = self._check_consistency(workflow, context, completed_steps)
                        if not consistency["pass"]:
                            print(f"[Workflow Consistency] Failed: {consistency['reason']}")
                            if consistency["action"] == "abort":
                                aborted = True
                                abort_reason = f"Consistency check '{consistency['rule']}' failed: {consistency['reason']}"
                                result["consistency_abort"] = True
                                break
                            elif consistency["action"] == "warn":
                                warnings.append(consistency)
                    if result.get("abort_workflow"):
                        aborted = True
                        abort_reason = f"Step '{step['id']}' in parallel group '{group_name}' failed with abort policy"
                        break

        # Build final result
        status = "aborted" if aborted else "completed"
        if aborted:
            status = "aborted"
        elif any(r.get("status") == "failed" for r in step_results.values()):
            status = "partial"

        return {
            "status": status,
            "workflow": workflow_name,
            "workflow_version": workflow.get("version", "unknown"),
            "steps": step_results,
            "execution_log": execution_log,
            "summary": self._build_summary(step_results),
            "aborted_reason": abort_reason,
            "consistency_warnings": warnings if warnings else None,
        }

    def _execute_single_step(self, step: dict, step_results: dict, context: dict, user_inputs: dict) -> dict:
        """Execute a single step with dependency and condition checks."""
        step_id = step["id"]

        # Check depends_on — all dependencies must have completed
        for dep in step.get("depends_on", []):
            dep_result = step_results.get(dep)
            if dep_result is None:
                return {
                    "step_id": step_id,
                    "status": "skipped",
                    "reason": f"dependency '{dep}' not found",
                }
            if dep_result.get("status") in ("failed", "aborted"):
                return {
                    "step_id": step_id,
                    "status": "skipped",
                    "reason": f"dependency '{dep}' failed",
                }

        # Check condition
        if "condition" in step:
            condition_met = self._check_condition(step["condition"], context)
            if not condition_met:
                print(f"[Workflow] Step '{step_id}' skipped: condition not met")
                return {
                    "step_id": step_id,
                    "status": "skipped",
                    "reason": "condition_not_met",
                    "condition": step["condition"],
                }

        # Build inputs from declared sources
        inputs = {}
        inputs_from = step.get("inputs_from", [])
        for src in inputs_from:
            if src == "user":
                inputs.update(user_inputs)
            elif src in step_results:
                src_data = step_results[src].get("data", {})
                if isinstance(src_data, dict):
                    inputs.update(src_data)

        # Apply input mapping (rename/transform user-friendly fields to script-expected fields)
        input_mapping = step.get("input_mapping", {})
        if input_mapping:
            for target_key, source_def in input_mapping.items():
                if isinstance(source_def, str):
                    # Simple rename: target_key gets value from source_def field
                    if source_def in inputs:
                        inputs[target_key] = inputs[source_def]
                elif isinstance(source_def, dict):
                    source = source_def.get("from", "")
                    default = source_def.get("default")
                    multiply_by = source_def.get("multiply_by")
                    if source and source in inputs:
                        val = inputs[source]
                        if multiply_by is not None:
                            try:
                                if multiply_by in inputs:
                                    val = float(val) * float(inputs[multiply_by])
                                else:
                                    val = float(val) * float(multiply_by)
                            except (ValueError, TypeError):
                                pass
                        inputs[target_key] = val
                    elif default is not None:
                        inputs[target_key] = default

        # Apply input defaults (for fields not provided by mapping)
        input_defaults = step.get("input_defaults", {})
        for key, val in input_defaults.items():
            if key not in inputs:
                inputs[key] = val

        # Add step_id to inputs for reference
        inputs["_workflow_step"] = step_id

        # Execute
        print(f"[Workflow] Executing step '{step_id}' with recipe '{step.get('recipe')}'")
        result = self._execute_step(step, inputs, context)

        # Update context with step result
        context[step_id] = result.get("data", result)

        return result


    def _check_consistency(self, workflow: dict, context: dict, completed_steps: list) -> dict:
        """P2a: 跨 step 一致性校验。
        
        Returns:
            {"pass": True} 或 {"pass": False, "rule": "...", "reason": "...", "action": "abort|warn|skip"}
        """
        checks = workflow.get("consistency_checks", [])
        if not checks:
            return {"pass": True}
        
        for rule in checks:
            rule_name = rule.get("name", "unnamed")
            source_step = rule.get("source_step")
            source_field = rule.get("source_field")
            operator = rule.get("operator")
            on_fail = rule.get("on_fail", "abort")
            
            # 检查 source_step 是否已执行
            if source_step not in completed_steps:
                continue
            
            # 获取 source 值 — use context[source_step] which is the step result data
            source_data = context.get(source_step, {})
            if not isinstance(source_data, dict):
                continue
            source_val = _resolve_field(source_field, source_data)
            if source_val is None:
                continue
            
            # 获取 target 值（fixed_value 或 target_step.field）
            if "fixed_value" in rule:
                target_val = rule["fixed_value"]
            else:
                target_step = rule.get("target_step")
                target_field = rule.get("target_field")
                if target_step not in completed_steps:
                    continue  # target 未执行，跳过
                target_data = context.get(target_step, {})
                if not isinstance(target_data, dict):
                    continue
                target_val = _resolve_field(target_field, target_data)
                if target_val is None:
                    continue
            
            # 执行比较（复用现有 OPERATORS 逻辑）
            handler = OPERATORS.get(operator)
            if handler is None:
                print(f"[Workflow Consistency] Unknown operator: {operator}")
                continue
            
            try:
                passed = handler(source_val, target_val)
            except (TypeError, ValueError):
                passed = False
            
            if not passed:
                return {
                    "pass": False,
                    "rule": rule_name,
                    "reason": f"{source_step}.{source_field}={source_val} 不满足 {operator} {target_val}",
                    "action": on_fail
                }
        
        return {"pass": True}

    def _build_summary(self, step_results: dict) -> dict:
        """Build a summary of workflow execution."""
        total = len(step_results)
        success = sum(1 for r in step_results.values() if r.get("status") == "success")
        skipped = sum(1 for r in step_results.values() if r.get("status") == "skipped")
        failed = sum(1 for r in step_results.values() if r.get("status") in ("failed", "abort"))
        fallback = sum(1 for r in step_results.values() if "fallback" in r.get("status", ""))

        # Collect all output data
        merged_data = {}
        for step_id, result in step_results.items():
            if result.get("status") == "success" and "data" in result:
                merged_data[step_id] = result["data"]

        return {
            "total_steps": total,
            "success": success,
            "skipped": skipped,
            "failed": failed,
            "fallback": fallback,
            "merged_data": merged_data,
        }
