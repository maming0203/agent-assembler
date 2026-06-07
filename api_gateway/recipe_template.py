"""
Standard Recipe Template — AutoCraft Engine SOP

Every auto-generated recipe should follow this structure.
The template provides validate_inputs(), run_simulation(), and run_stress_test()
methods that the engineering-stage-agent can adapt for any domain.

Usage:
    1. Copy this template into a new skill file.
    2. Fill in the domain-specific logic in each method.
    3. Ensure the companion recipe JSON matches recipe_schema.json.
"""

import json
import os
import sys
from typing import Any


class RecipeTemplate:
    """Base template for auto-generated recipes. Override methods for domain logic."""

    def __init__(self, recipe_path: str):
        """Load and validate the companion recipe JSON."""
        self.recipe_path = recipe_path
        self.recipe = self._load_recipe()

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #
    def _load_recipe(self) -> dict:
        if not os.path.exists(self.recipe_path):
            raise FileNotFoundError(f"Recipe not found: {self.recipe_path}")
        with open(self.recipe_path, encoding="utf-8") as f:
            return json.load(f)

    def _validate_recipe_structure(self) -> list[str]:
        """Return a list of validation errors (empty = valid)."""
        errors: list[str] = []
        r = self.recipe

        # Required fields
        if not isinstance(r.get("name"), str) or not r["name"]:
            errors.append("'name' must be a non-empty string")
        if not isinstance(r.get("trigger_keywords"), list) or not r["trigger_keywords"]:
            errors.append("'trigger_keywords' must be a non-empty list of strings")
        elif not all(isinstance(kw, str) for kw in r["trigger_keywords"]):
            errors.append("All items in 'trigger_keywords' must be strings")

        # Optional fields type checks
        if "skills" in r and not isinstance(r["skills"], list):
            errors.append("'skills' must be a list of strings")
        if "notes" in r and not isinstance(r["notes"], str):
            errors.append("'notes' must be a string")
        if "routing" in r and not isinstance(r["routing"], dict):
            errors.append("'routing' must be an object")
        if "engine_config" in r and not isinstance(r["engine_config"], dict):
            errors.append("'engine_config' must be an object")

        return errors

    # ------------------------------------------------------------------ #
    #  Public API — override these in generated recipes
    # ------------------------------------------------------------------ #
    def validate_inputs(self, user_query: str) -> dict[str, Any]:
        """
        Validate and normalize user inputs before execution.

        Args:
            user_query: The raw query string from the user.

        Returns:
            dict with keys:
                - valid (bool): Whether inputs pass validation.
                - normalized (str): Sanitized / enriched query.
                - errors (list[str]): Any validation error messages.
        """
        errors: list[str] = []

        if not user_query or not user_query.strip():
            errors.append("Query cannot be empty")

        # Check if any trigger keyword matches
        matched_kw = None
        for kw in self.recipe.get("trigger_keywords", []):
            if kw.lower() in user_query.lower():
                matched_kw = kw
                break

        if not matched_kw:
            errors.append(
                f"No trigger keyword matched. Expected one of: "
                f"{self.recipe.get('trigger_keywords', [])}"
            )

        return {
            "valid": len(errors) == 0,
            "normalized": user_query.strip(),
            "matched_keyword": matched_kw,
            "errors": errors,
        }

    def run_simulation(self, user_query: str) -> dict[str, Any]:
        """
        Execute the recipe logic in simulation / dry-run mode.

        Override this method with domain-specific processing.
        This is called during the AutoCraft generation to verify
        the recipe produces a meaningful result before deployment.

        Args:
            user_query: The validated user query.

        Returns:
            dict with keys:
                - status (str): "ok" | "error"
                - output (str): The simulated result.
                - steps (list[str]): Execution steps taken.
        """
        # ---- DOMAIN-SPECIFIC LOGIC GOES HERE ----
        # Replace this stub with actual processing:
        #   1. Parse the query
        #   2. Load any required data / models
        #   3. Run calculations or transformations
        #   4. Format the result

        return {
            "status": "ok",
            "output": f"[SIMULATION] Processed query: {user_query}",
            "steps": [
                "Loaded recipe configuration",
                "Validated inputs",
                "Ran simulation logic",
                "Formatted output",
            ],
        }

    def run_stress_test(self, n_iterations: int = 10) -> dict[str, Any]:
        """
        Run the recipe multiple times with varied inputs to check stability.

        Override to provide domain-specific test cases.

        Args:
            n_iterations: Number of test runs.

        Returns:
            dict with keys:
                - total_runs (int)
                - passed (int)
                - failed (int)
                - results (list[dict]): Per-run outcome.
        """
        # ---- DOMAIN-SPECIFIC TEST CASES GO HERE ----
        test_cases = [
            f"Test query #{i}: {self.recipe.get('name', 'recipe')}"
            for i in range(n_iterations)
        ]

        results: list[dict] = []
        passed = 0
        failed = 0

        for tc in test_cases:
            try:
                sim = self.run_simulation(tc)
                if sim.get("status") == "ok":
                    passed += 1
                    results.append({"input": tc, "status": "passed"})
                else:
                    failed += 1
                    results.append({"input": tc, "status": "failed", "error": sim.get("output")})
            except Exception as e:
                failed += 1
                results.append({"input": tc, "status": "error", "error": str(e)})

        return {
            "total_runs": n_iterations,
            "passed": passed,
            "failed": failed,
            "results": results,
        }


# ------------------------------------------------------------------ #
#  CLI entry point for manual testing
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python recipe_template.py <recipe.json> [query]")
        sys.exit(1)

    recipe_file = sys.argv[1]
    query = sys.argv[2] if len(sys.argv) > 2 else "Test query"

    recipe = RecipeTemplate(recipe_file)

    # Step 1: Validate recipe structure
    errs = recipe._validate_recipe_structure()
    if errs:
        print("Recipe validation FAILED:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)
    print("Recipe structure: OK")

    # Step 2: Validate inputs
    inp = recipe.validate_inputs(query)
    print(f"Input validation: {'OK' if inp['valid'] else 'FAILED'}")
    if not inp["valid"]:
        for e in inp["errors"]:
            print(f"  - {e}")

    # Step 3: Run simulation
    sim = recipe.run_simulation(query)
    print(f"Simulation: {sim['status']}")
    print(f"Output: {sim['output']}")

    # Step 4: Stress test
    stress = recipe.run_stress_test(n_iterations=5)
    print(f"Stress test: {stress['passed']}/{stress['total_runs']} passed")
