def validate_sample(sample):
    """Structurally validate one engagement sample (the real validation happens inside AFSIM)."""
    errors = []
    scenario = (sample.get("scenario_text") or "") if isinstance(sample, dict) else ""
    if "platform" not in scenario.lower():
        errors.append("scenario missing platform definition")
    if "objective" not in scenario.lower() and "# objective" not in scenario.lower():
        errors.append("scenario missing explicit objective")
    checks = {"has_platform": "platform" in scenario.lower(),
              "has_objective": "objective" in scenario.lower()}
    return {"valid": len(errors) == 0, "errors": errors, "checks": checks}
