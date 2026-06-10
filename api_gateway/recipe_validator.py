"""
AutoCraft v3 Recipe Validator

Validates that auto-generated recipes contain all required artifacts
and that Python scripts execute correctly before allowing入库.

Usage:
    from .recipe_validator import RecipeValidator
    validator = RecipeValidator(recipe_dir)
    report = validator.validate_full(recipe_name, recipe_data)
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ValidationResult:
    """Single validation check result."""
    check: str
    passed: bool
    message: str = ""
    details: str = ""


@dataclass
class ValidationReport:
    """Full validation report for a recipe."""
    recipe_name: str
    overall_passed: bool = False
    checks: List[ValidationResult] = field(default_factory=list)
    artifacts_found: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def add(self, check: str, passed: bool, message: str = "", details: str = ""):
        self.checks.append(ValidationResult(check, passed, message, details))
        if not passed:
            self.errors.append(f"[{check}] {message}")

    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c.passed)
        status = "PASS" if self.overall_passed else "FAIL"
        return f"[{status}] {self.recipe_name}: {passed}/{total} checks passed"


class RecipeValidator:
    """
    Validates auto-generated recipes for completeness and correctness.

    Required artifacts for a valid "hard" recipe:
    1. recipe JSON (with all required fields)
    2. Python script (with validate_inputs + run_simulation + run_stress_test)
    3. SKILL.md (with YAML frontmatter + GEO optimization)
    4. mcp.json (with input/output schema)
    """

    def __init__(self, recipe_dir: str):
        self.recipe_dir = recipe_dir

    def validate_full(
        self,
        recipe_name: str,
        recipe_data: dict,
        script_path: str = "",
        skill_md_path: str = "",
        mcp_json_path: str = "",
    ) -> ValidationReport:
        """Run full validation suite on a recipe and its artifacts."""
        report = ValidationReport(recipe_name=recipe_name)

        # Phase 1: JSON schema validation
        report = self._validate_json(report, recipe_data)

        # Phase 2: Artifact existence checks
        report = self._validate_artifacts(
            report, script_path, skill_md_path, mcp_json_path
        )

        # Phase 3: Script content validation
        if script_path and os.path.exists(script_path):
            report = self._validate_script_content(report, script_path)

        # Phase 4: Script execution test
        if script_path and os.path.exists(script_path):
            report = self._validate_script_execution(report, script_path)

        # Phase 5: SKILL.md content validation
        if skill_md_path and os.path.exists(skill_md_path):
            report = self._validate_skill_md(report, skill_md_path)

        # Phase 6: mcp.json validation
        if mcp_json_path and os.path.exists(mcp_json_path):
            report = self._validate_mcp_json(report, mcp_json_path)

        report.overall_passed = len(report.errors) == 0
        return report

    # --------------------------------------------------------------- #
    #  Phase 1: JSON validation
    # --------------------------------------------------------------- #
    def _validate_json(self, report: ValidationReport, data: dict) -> ValidationReport:
        """Validate recipe JSON has all required fields."""
        # Required fields
        for field_name in ("name", "trigger_keywords"):
            if field_name not in data:
                report.add(
                    f"json.{field_name}",
                    False,
                    f"Missing required field: '{field_name}'",
                )
            elif not data[field_name]:
                report.add(
                    f"json.{field_name}",
                    False,
                    f"Field '{field_name}' is empty",
                )
            else:
                report.add(f"json.{field_name}", True)

        # trigger_keywords must be a list with >= 2 items
        tk = data.get("trigger_keywords")
        if isinstance(tk, list):
            if len(tk) >= 2:
                report.add("json.trigger_keywords.count", True)
            else:
                report.add(
                    "json.trigger_keywords.count",
                    False,
                    f"Need >= 2 keywords, got {len(tk)}",
                )

        # Hard recipe: must have script_path
        sp = data.get("script_path", "")
        if sp and isinstance(sp, str) and sp.strip():
            report.add("json.script_path", True)
        else:
            report.add("json.script_path", False, "No script_path — recipe has no executable core")

        # YAML frontmatter metadata
        for meta_field in ("version", "intent_description", "scenario_tags"):
            if meta_field in data and data[meta_field]:
                report.add(f"json.{meta_field}", True)
            else:
                report.add(
                    f"json.{meta_field}",
                    False,
                    f"Missing metadata: '{meta_field}'",
                )

        return report

    # --------------------------------------------------------------- #
    #  Phase 2: Artifact existence
    # --------------------------------------------------------------- #
    def _validate_artifacts(
        self,
        report: ValidationReport,
        script_path: str,
        skill_md_path: str,
        mcp_json_path: str,
    ) -> ValidationReport:
        """Check that all expected artifact files exist."""
        artifacts = {
            "script": script_path,
            "skill_md": skill_md_path,
            "mcp_json": mcp_json_path,
        }
        for name, path in artifacts.items():
            exists = bool(path and os.path.exists(path))
            report.artifacts_found[name] = exists
            report.add(
                f"artifact.{name}",
                exists,
                f"File {'found' if exists else 'NOT found'}: {path or '(none)'}",
            )
        return report

    # --------------------------------------------------------------- #
    #  Phase 3: Script content validation
    # --------------------------------------------------------------- #
    def _validate_script_content(
        self, report: ValidationReport, script_path: str
    ) -> ValidationReport:
        """Validate Python script has required methods and structure."""
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            report.add("script.read", False, f"Cannot read script: {e}")
            return report

        # Must have validate_inputs
        if "def validate_inputs" in content:
            report.add("script.validate_inputs", True)
        else:
            report.add("script.validate_inputs", False, "Missing validate_inputs() method")

        # Must have run_simulation
        if "def run_simulation" in content:
            report.add("script.run_simulation", True)
        else:
            report.add("script.run_simulation", False, "Missing run_simulation() method")

        # Must have run_stress_test
        if "def run_stress_test" in content:
            report.add("script.run_stress_test", True)
        else:
            report.add("script.run_stress_test", False, "Missing run_stress_test() method")

        # Must have --json CLI support
        if "--json" in content or "'--json'" in content or '"--json"' in content:
            report.add("script.cli_json", True)
        else:
            report.add("script.cli_json", False, "Missing --json CLI entry point")

        # Must import json
        if "import json" in content:
            report.add("script.import_json", True)
        else:
            report.add("script.import_json", False, "Missing 'import json'")

        # Syntax check
        try:
            compile(content, script_path, "exec")
            report.add("script.syntax", True, "Python syntax OK")
        except SyntaxError as e:
            report.add("script.syntax", False, f"Syntax error: {e}")

        return report

    # --------------------------------------------------------------- #
    #  Phase 4: Script execution test
    # --------------------------------------------------------------- #
    def _validate_script_execution(
        self, report: ValidationReport, script_path: str
    ) -> ValidationReport:
        """Run the script's stress test and verify it passes."""
        try:
            result = subprocess.run(
                [sys.executable, script_path, "--test"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                report.add("script.execution", True, "Stress test passed")
                # Parse pass/fail from output
                output = result.stdout
                match = re.search(r"Passed:\s*(\d+)", output)
                if match:
                    passed = int(match.group(1))
                    report.add("script.test_count", True, f"{passed} tests passed")
            else:
                report.add(
                    "script.execution",
                    False,
                    f"Stress test failed (exit {result.returncode})",
                    result.stderr[:200],
                )
        except subprocess.TimeoutExpired:
            report.add("script.execution", False, "Stress test timed out (30s)")
        except FileNotFoundError:
            report.add("script.execution", False, f"Python interpreter not found")
        except Exception as e:
            report.add("script.execution", False, f"Execution error: {e}")

        return report

    # --------------------------------------------------------------- #
    #  Phase 5: SKILL.md validation
    # --------------------------------------------------------------- #
    def _validate_skill_md(
        self, report: ValidationReport, skill_md_path: str
    ) -> ValidationReport:
        """Validate SKILL.md has YAML frontmatter and required sections."""
        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            report.add("skill_md.read", False, f"Cannot read: {e}")
            return report

        # Must have YAML frontmatter
        if content.startswith("---"):
            report.add("skill_md.frontmatter", True)
            # Check for name in frontmatter
            if re.search(r"^name:\s*\S+", content, re.MULTILINE):
                report.add("skill_md.frontmatter.name", True)
            else:
                report.add("skill_md.frontmatter.name", False, "Missing 'name:' in frontmatter")
        else:
            report.add("skill_md.frontmatter", False, "Missing YAML frontmatter (---)")

        # Must have trigger keywords section
        if "触发关键词" in content or "trigger" in content.lower():
            report.add("skill_md.triggers", True)
        else:
            report.add("skill_md.triggers", False, "Missing trigger keywords section")

        # Must have Few-shot examples
        if "Few-shot" in content or "示例" in content:
            report.add("skill_md.few_shot", True)
        else:
            report.add("skill_md.few_shot", False, "Missing Few-shot examples")

        # Must have GEO optimization
        if "GEO" in content or "意图" in content:
            report.add("skill_md.geo", True)
        else:
            report.add("skill_md.geo", False, "Missing GEO optimization section")

        return report

    # --------------------------------------------------------------- #
    #  Phase 6: mcp.json validation
    # --------------------------------------------------------------- #
    def _validate_mcp_json(
        self, report: ValidationReport, mcp_json_path: str
    ) -> ValidationReport:
        """Validate mcp.json has required structure."""
        try:
            with open(mcp_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            report.add("mcp_json.parse", False, f"Invalid JSON: {e}")
            return report
        except Exception as e:
            report.add("mcp_json.read", False, f"Cannot read: {e}")
            return report

        report.add("mcp_json.parse", True, "Valid JSON")

        # Must have name and input_schema
        if "name" in data and data["name"]:
            report.add("mcp_json.name", True)
        else:
            report.add("mcp_json.name", False, "Missing 'name'")

        if "input_schema" in data:
            report.add("mcp_json.input_schema", True)
        else:
            report.add("mcp_json.input_schema", False, "Missing 'input_schema'")

        if "output_schema" in data:
            report.add("mcp_json.output_schema", True)
        else:
            report.add("mcp_json.output_schema", False, "Missing 'output_schema'")

        if "execution" in data:
            report.add("mcp_json.execution", True)
        else:
            report.add("mcp_json.execution", False, "Missing 'execution' config")

        return report
