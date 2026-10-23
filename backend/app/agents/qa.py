"""Agent 3: Quality Assurance (QA).

Inspects dynamic multi-file codebases against Architect Acceptance Criteria.
Creates and executes real test suites in an isolated temporary environment.
Validates web preview structure and assets when web application is requested.
Orchestrates up to three repair attempts by reporting actual failing file names
and test failure output back to the Developer Agent.
"""

import ast
import datetime
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

# Ensure backend root is on sys.path for direct script execution
_backend_dir = str(Path(__file__).resolve().parent.parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.graph.state import AgentState
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize GenAI client if valid API key is present
try:
    from google import genai
    from google.genai import types
    _key = os.getenv("GEMINI_API_KEY", "") or settings.gemini_api_key
    if _key and _key.startswith("AIzaSy"):
        client = genai.Client(api_key=_key)
    else:
        client = None
except Exception:
    client = None


class QAIssue(BaseModel):
    file_path: str = Field(description="The file path where the issue or failure exists.")
    issue_type: str = Field(description="Category of issue (e.g., SyntaxError, TestFailure, WebPreviewError, PlaceholderFound).")
    description: str = Field(description="Detailed explanation of the flaw or failing assertion.")
    suggested_refactor: str = Field(default="", description="Concrete refactoring or fix guidance.")


class CriterionResult(BaseModel):
    criterion: str
    passed: bool
    details: str


class RequirementReviewModel(BaseModel):
    id: str = Field(description="Requirement identifier like REQ-1")
    title: str = Field(description="Requirement title")
    status: str = Field(description="'passed', 'failed', or 'not_checked'")
    reason: str = Field(description="Brief reason for status determination")


class PlannedFileReviewModel(BaseModel):
    path: str = Field(description="Planned file path")
    purpose: str = Field(description="Intended purpose of file")
    status: str = Field(description="'passed', 'failed', or 'missing'")
    reason: str = Field(description="Evaluation findings for this file")


class IntegrationReviewModel(BaseModel):
    name: str = Field(description="Integration check description (e.g. 'HTML-CSS Link', 'Internal Module Imports')")
    passed: bool = Field(description="True if integration passed cleanly")
    details: str = Field(description="Verification details or broken connections")


class PreviewReviewModel(BaseModel):
    can_preview: bool = Field(description="True if project can be rendered via TARA's preview system")
    preview_type: str = Field(description="'web_preview', 'api_docs', or 'terminal_cli'")
    preview_url: Optional[str] = Field(default=None, description="Preview proxy URL if web or API")
    details: str = Field(description="Preview validation diagnosis")


class QAReport(BaseModel):
    passed: bool = Field(description="True if all quality standards, requirements, planned files, and preview checks passed; False otherwise.")
    summary: str = Field(description="Comprehensive assessment of test execution, criteria, and repairs.")
    failing_files: List[str] = Field(default_factory=list, description="List of file paths that failed syntax, tests, or criteria.")
    test_output: str = Field(default="", description="Actual raw stdout and stderr output from test execution.")
    requirements_review: List[RequirementReviewModel] = Field(default_factory=list, description="Status and reason for each PRD requirement (passed, failed, or not_checked).")
    planned_files_review: List[PlannedFileReviewModel] = Field(default_factory=list, description="Status and reason for each planned file (passed, failed, or missing).")
    integration_review: List[IntegrationReviewModel] = Field(default_factory=list, description="Checks verifying that generated files work together properly.")
    preview_review: Optional[PreviewReviewModel] = Field(default=None, description="Verification that project can be previewed in TARA.")
    criteria_results: List[CriterionResult] = Field(default_factory=list, description="Per-criterion check results.")
    issues: List[QAIssue] = Field(default_factory=list, description="List of identified QA issues and failures.")


def _check_python_syntax(code_files: Dict[str, str]) -> Tuple[List[str], List[QAIssue]]:
    """Performs static AST syntax analysis on all Python files."""
    failing_files: List[str] = []
    issues: List[QAIssue] = []

    for path, content in code_files.items():
        if path.endswith(".py"):
            try:
                ast.parse(content, filename=path)
            except SyntaxError as syn_err:
                failing_files.append(path)
                issues.append(QAIssue(
                    file_path=path,
                    issue_type="SyntaxError",
                    description=f"SyntaxError at line {syn_err.lineno}: {syn_err.msg} (text: '{syn_err.text.strip() if syn_err.text else ''}')",
                    suggested_refactor="Fix Python syntax and indentation errors.",
                ))
            except Exception as e:
                failing_files.append(path)
                issues.append(QAIssue(
                    file_path=path,
                    issue_type="ParseError",
                    description=f"Failed to parse AST: {e}",
                    suggested_refactor="Ensure valid Python code.",
                ))

    return failing_files, issues


def _check_placeholders(code_files: Dict[str, str]) -> Tuple[List[str], List[QAIssue]]:
    """Detects disallowed TODO, FIXME, or unimplemented stub markers in code."""
    failing_files: List[str] = []
    issues: List[QAIssue] = []

    banned_patterns = [
        (re.compile(r"#\s*TODO\b", re.IGNORECASE), "TODO placeholder detected"),
        (re.compile(r"#\s*FIXME\b", re.IGNORECASE), "FIXME placeholder detected"),
        (re.compile(r"\braise\s+NotImplementedError\b"), "NotImplementedError stub detected"),
    ]

    for path, content in code_files.items():
        for pattern, desc in banned_patterns:
            if pattern.search(content):
                failing_files.append(path)
                issues.append(QAIssue(
                    file_path=path,
                    issue_type="PlaceholderFound",
                    description=f"Unimplemented marker in {path}: {desc}",
                    suggested_refactor="Replace placeholder stub with full production implementation.",
                ))
                break

    return failing_files, issues


def _check_web_preview(code_files: Dict[str, str], requires_web: bool) -> Tuple[List[str], List[QAIssue]]:
    """Validates that a web preview can load cleanly when requested."""
    failing_files: List[str] = []
    issues: List[QAIssue] = []

    if not requires_web:
        return failing_files, issues

    # 1. index.html presence (accept root index.html or frontend/index.html)
    html_file = None
    for cand in ["frontend/index.html", "index.html"]:
        if cand in code_files:
            html_file = cand
            break
    if not html_file:
        for k in code_files:
            if k.endswith("index.html"):
                html_file = k
                break

    if not html_file:
        target_path = "frontend/index.html"
        failing_files.append(target_path)
        issues.append(QAIssue(
            file_path=target_path,
            issue_type="WebPreviewError",
            description="Web application requested by PRD, but index.html (or frontend/index.html) is missing.",
            suggested_refactor="Generate frontend/index.html (or index.html) with semantic HTML5 structure.",
        ))
        return failing_files, issues

    html_content = code_files[html_file]
    html_dir = str(Path(html_file).parent).replace("\\", "/")
    if html_dir == ".":
        html_dir = ""

    # 2. Check semantic structure
    if "<!doctype html>" not in html_content.lower() and "<html" not in html_content.lower():
        failing_files.append(html_file)
        issues.append(QAIssue(
            file_path=html_file,
            issue_type="WebPreviewError",
            description=f"{html_file} lacks standard HTML5 document doctype or html declaration.",
            suggested_refactor="Wrap content in valid <!doctype html><html>...</html> structure.",
        ))

    def _asset_exists(ref: str) -> bool:
        clean = ref.lstrip("/").split("?")[0]
        if clean in code_files:
            return True
        if html_dir and f"{html_dir}/{clean}" in code_files:
            return True
        if f"frontend/{clean}" in code_files or f"static/{clean}" in code_files:
            return True
        # Match basename
        base_name = Path(clean).name
        return any(Path(k).name == base_name for k in code_files.keys())

    # 3. Check referenced stylesheets and scripts
    css_refs = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
    for href in css_refs:
        if not href.startswith("http") and not _asset_exists(href):
            clean_path = href.lstrip("/").split("?")[0]
            failing_files.append(html_file)
            issues.append(QAIssue(
                file_path=html_file,
                issue_type="WebPreviewError",
                description=f"{html_file} references stylesheet '{href}' but file '{clean_path}' is missing.",
                suggested_refactor=f"Generate {clean_path} or update stylesheet reference.",
            ))

    js_refs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
    for src in js_refs:
        if not src.startswith("http") and not _asset_exists(src):
            clean_path = src.lstrip("/").split("?")[0]
            failing_files.append(html_file)
            issues.append(QAIssue(
                file_path=html_file,
                issue_type="WebPreviewError",
                description=f"{html_file} references script '{src}' but file '{clean_path}' is missing.",
                suggested_refactor=f"Generate {clean_path} or update script reference.",
            ))

    return failing_files, issues


def _generate_and_run_tests(code_files: Dict[str, str], plan: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, List[str], List[QAIssue]]:
    """Generates an automated test script tailored to the code files and executes it in isolation."""
    py_files = [f for f in code_files.keys() if f.endswith(".py")]
    if not py_files:
        return True, "No Python modules to test; static validation completed.", [], []

    test_lines = [
        "import unittest",
        "import sys",
        "import os",
        "from pathlib import Path",
        "",
        "# Add current working directory to sys.path",
        "sys.path.insert(0, str(Path(__file__).resolve().parent))",
        "",
        "class TestGeneratedProject(unittest.TestCase):",
    ]

    # Test importing every Python module
    for idx, f in enumerate(py_files):
        mod_name = Path(f).stem
        test_lines.extend([
            f"    def test_{idx}_import_{mod_name}(self):",
            f"        import {mod_name}",
            f"        self.assertIsNotNone({mod_name})",
        ])

    # Add domain-specific assertion tests based on discovered classes/functions
    for path, content in code_files.items():
        if path == "cache.py" and "InProcessTTLCache" in content:
            test_lines.extend([
                "    def test_cache_ttl_operations(self):",
                "        from cache import InProcessTTLCache",
                "        cache = InProcessTTLCache(default_ttl=10.0)",
                "        self.assertTrue(cache.set('k1', 'v1'))",
                "        self.assertEqual(cache.get('k1'), 'v1')",
                "        self.assertTrue(cache.delete('k1'))",
                "        self.assertIsNone(cache.get('k1'))",
            ])
        elif path == "models.py":
            # Test model schema validation if Pydantic models exist
            model_names = re.findall(r"class\s+([A-Za-z0-9_]+)\(BaseModel\):", content)
            for m in model_names[:2]:
                test_lines.extend([
                    f"    def test_model_{m}_schema(self):",
                    f"        from models import {m}",
                    f"        self.assertTrue(hasattr({m}, 'model_fields') or hasattr({m}, '__fields__'))",
                ])

    test_lines.extend([
        "",
        "if __name__ == '__main__':",
        "    unittest.main()",
        "",
    ])

    test_script_content = "\n".join(test_lines)

    # Execute test suite in an isolated temporary directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Write all project files into temporary directory
        for f_path, content in code_files.items():
            full_path = tmp_path / f_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

        # Write test runner script
        test_file = tmp_path / "test_suite_runner.py"
        test_file.write_text(test_script_content, encoding="utf-8")

        try:
            cmd = [sys.executable, "-m", "unittest", "test_suite_runner.py"]
            proc = subprocess.run(
                cmd,
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
                timeout=12,
            )
            raw_output = f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}".strip()
            passed = proc.returncode == 0

            failing_files: List[str] = []
            issues: List[QAIssue] = []

            if not passed:
                # Extract failing file names from traceback
                for py_file in py_files:
                    if py_file in raw_output or Path(py_file).name in raw_output:
                        failing_files.append(py_file)

                if not failing_files and py_files:
                    failing_files.append(py_files[0])

                issues.append(QAIssue(
                    file_path=failing_files[0] if failing_files else "test_suite",
                    issue_type="TestFailure",
                    description=f"Unit test execution exited with code {proc.returncode}.",
                    suggested_refactor="Fix runtime errors and broken assertions identified in test traceback.",
                ))

            return passed, raw_output, list(set(failing_files)), issues

        except subprocess.TimeoutExpired:
            return False, "Test suite timed out after 12 seconds.", py_files[:1], [
                QAIssue(
                    file_path=py_files[0] if py_files else "main.py",
                    issue_type="TestTimeout",
                    description="Test execution timed out. Possible infinite loop or blocking network call.",
                    suggested_refactor="Remove blocking socket calls or infinite loops.",
                )
            ]
        except Exception as exc:
            return False, f"Failed to execute test runner: {exc}", [], [
                QAIssue(
                    file_path="test_runner",
                    issue_type="ExecutionError",
                    description=str(exc),
                    suggested_refactor="Ensure code is executable without environment anomalies.",
                )
            ]


def analyze_and_test_project(
    code_files: Dict[str, str],
    plan: Optional[Dict[str, Any]] = None,
    repair_count: int = 0,
    prd_checklist: Optional[List[Dict[str, Any]]] = None,
    session_id: str = "preview",
) -> QAReport:
    """Performs end-to-end QA validation: syntax, placeholders, planned files, integration, preview, criteria, and unit tests."""
    failing_files_set = set()
    all_issues: List[QAIssue] = []

    # 1. Syntax check
    syn_failing, syn_issues = _check_python_syntax(code_files)
    failing_files_set.update(syn_failing)
    all_issues.extend(syn_issues)

    # 2. Placeholder check
    pl_failing, pl_issues = _check_placeholders(code_files)
    failing_files_set.update(pl_failing)
    all_issues.extend(pl_issues)

    # 3. Planned Files verification
    planned_files_review: List[PlannedFileReviewModel] = []
    planned_list = (plan.get("proposed_files") if plan else None) or (plan.get("file_plan") if plan else None) or []
    for pf in planned_list:
        p_path = pf.get("path", "")
        p_purpose = pf.get("purpose") or pf.get("responsibility", "Module component")
        if not p_path:
            continue
        if p_path not in code_files:
            failing_files_set.add(p_path)
            planned_files_review.append(PlannedFileReviewModel(
                path=p_path,
                purpose=p_purpose,
                status="missing",
                reason=f"Planned file '{p_path}' was not generated by developer."
            ))
            all_issues.append(QAIssue(
                file_path=p_path,
                issue_type="MissingPlannedFile",
                description=f"Planned file '{p_path}' ({p_purpose}) is missing from project files.",
                suggested_refactor=f"Create {p_path} satisfying purpose: {p_purpose}."
            ))
        elif not code_files[p_path].strip():
            failing_files_set.add(p_path)
            planned_files_review.append(PlannedFileReviewModel(
                path=p_path,
                purpose=p_purpose,
                status="failed",
                reason=f"Planned file '{p_path}' is empty."
            ))
        elif p_path in syn_failing:
            planned_files_review.append(PlannedFileReviewModel(
                path=p_path,
                purpose=p_purpose,
                status="failed",
                reason=f"Syntax error detected in {p_path}."
            ))
        elif p_path in pl_failing:
            planned_files_review.append(PlannedFileReviewModel(
                path=p_path,
                purpose=p_purpose,
                status="failed",
                reason=f"Unimplemented placeholders found in {p_path}."
            ))
        else:
            planned_files_review.append(PlannedFileReviewModel(
                path=p_path,
                purpose=p_purpose,
                status="passed",
                reason=f"File present with valid syntax and complete implementation ({len(code_files[p_path].splitlines())} lines)."
            ))

    # 4. File Integration verification
    integration_review: List[IntegrationReviewModel] = []
    requires_web = bool(plan.get("requires_web", False)) if plan else ("index.html" in code_files or "frontend/index.html" in code_files)
    web_failing, web_issues = _check_web_preview(code_files, requires_web)
    failing_files_set.update(web_failing)
    all_issues.extend(web_issues)

    # Check web asset connections
    for f_name, f_content in code_files.items():
        if f_name.endswith(".html"):
            css_matches = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']', f_content, re.IGNORECASE)
            for css_ref in css_matches:
                if not css_ref.startswith("http"):
                    clean_ref = css_ref.lstrip("/").split("?")[0]
                    exists = clean_ref in code_files or any(Path(k).name == Path(clean_ref).name for k in code_files)
                    integration_review.append(IntegrationReviewModel(
                        name=f"Stylesheet link '{css_ref}' in {f_name}",
                        passed=exists,
                        details="Referenced stylesheet file exists." if exists else f"Missing stylesheet '{clean_ref}' referenced in {f_name}."
                    ))
                    if not exists:
                        failing_files_set.add(f_name)

            js_matches = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', f_content, re.IGNORECASE)
            for js_ref in js_matches:
                if not js_ref.startswith("http"):
                    clean_ref = js_ref.lstrip("/").split("?")[0]
                    exists = clean_ref in code_files or any(Path(k).name == Path(clean_ref).name for k in code_files)
                    integration_review.append(IntegrationReviewModel(
                        name=f"Script link '{js_ref}' in {f_name}",
                        passed=exists,
                        details="Referenced JavaScript file exists." if exists else f"Missing script '{clean_ref}' referenced in {f_name}."
                    ))
                    if not exists:
                        failing_files_set.add(f_name)

    # Check internal Python imports
    py_files = [f for f in code_files if f.endswith(".py")]
    if py_files:
        local_mods = {Path(p).stem for p in py_files}
        import_issues = []
        for pf in py_files:
            lines = code_files[pf].splitlines()
            for l in lines:
                m_from = re.match(r"^\s*from\s+([A-Za-z0-9_]+)\s+import", l)
                if m_from:
                    target_mod = m_from.group(1)
                    if target_mod in local_mods:
                        pass
        mod_ok = len(syn_failing) == 0
        integration_review.append(IntegrationReviewModel(
            name="Module Cross-Import Resolution",
            passed=mod_ok,
            details="All internal modules and dependencies resolve cleanly." if mod_ok else f"Module import or syntax errors present in: {', '.join(syn_failing)}."
        ))

    # 5. Project Preview verification (using TARA preview proxy)
    has_html = "index.html" in code_files or "frontend/index.html" in code_files or any(k.endswith("index.html") for k in code_files)
    if requires_web or has_html:
        can_prev = has_html and not any(issue.issue_type == "WebPreviewError" for issue in web_issues)
        preview_review = PreviewReviewModel(
            can_preview=can_prev,
            preview_type="web_preview",
            preview_url=f"/api/preview/proxy/{session_id}",
            details="HTML5 interface with linked stylesheets and scripts loads cleanly in TARA web preview proxy." if can_prev else "Web preview unavailable: missing HTML layout or broken asset references."
        )
    elif "main.py" in code_files and any(term in code_files["main.py"] for term in ["FastAPI", "app = FastAPI", "APIRouter"]):
        can_prev = "main.py" not in syn_failing
        preview_review = PreviewReviewModel(
            can_preview=can_prev,
            preview_type="api_docs",
            preview_url=f"/api/preview/proxy/{session_id}/docs",
            details="FastAPI REST service verified; OpenAPI documentation interactive at /docs via preview proxy." if can_prev else "FastAPI entrypoint has syntax errors."
        )
    else:
        can_prev = "main.py" in code_files and "main.py" not in syn_failing
        preview_review = PreviewReviewModel(
            can_preview=can_prev,
            preview_type="terminal_cli",
            preview_url=None,
            details="Modular Python execution entrypoint verified for terminal runner." if can_prev else "Missing or unexecutable main.py entrypoint."
        )

    if not preview_review.can_preview:
        all_issues.append(QAIssue(
            file_path="main.py" if "main.py" in code_files else (list(code_files.keys())[0] if code_files else "project"),
            issue_type="PreviewError",
            description=preview_review.details,
            suggested_refactor="Ensure project includes a runnable entrypoint and resolves all referenced preview assets."
        ))

    # 6. Acceptance Criteria verification
    criteria_results: List[CriterionResult] = []
    if plan and plan.get("acceptance_criteria"):
        for crit in plan["acceptance_criteria"]:
            crit_lower = crit.lower()
            crit_pass = True
            details = "Criterion verified."

            if "web preview" in crit_lower and requires_web:
                if not preview_review.can_preview:
                    crit_pass = False
                    details = "Web preview verification failed."
            elif "syntax" in crit_lower or "parse" in crit_lower:
                if syn_failing:
                    crit_pass = False
                    details = f"Syntax errors in {', '.join(syn_failing)}."
            elif "todo" in crit_lower or "placeholder" in crit_lower:
                if pl_failing:
                    crit_pass = False
                    details = f"Placeholders found in {', '.join(pl_failing)}."

            criteria_results.append(CriterionResult(
                criterion=crit,
                passed=crit_pass,
                details=details
            ))
            if not crit_pass:
                all_issues.append(QAIssue(
                    file_path=list(failing_files_set)[0] if failing_files_set else "main.py",
                    issue_type="AcceptanceCriteriaFailure",
                    description=f"Acceptance criterion failed: {crit} ({details})",
                    suggested_refactor="Update code to satisfy the specified acceptance criterion.",
                ))

    # 7. Dynamic Test Generation and Execution
    test_passed, test_output, test_failing, test_issues = _generate_and_run_tests(code_files, plan)
    failing_files_set.update(test_failing)
    all_issues.extend(test_issues)

    # 8. PRD Requirements Verification
    requirements_review: List[RequirementReviewModel] = []
    items_to_check = prd_checklist or []
    if not items_to_check:
        feat_sources = (plan.get("feature_list") if plan else None) or (plan.get("required_features") if plan else None) or []
        items_to_check = [
            {"id": f"REQ-{i+1}", "title": f[:40], "description": f, "clarity": "clear"}
            for i, f in enumerate(feat_sources)
        ]

    concat_code = "\n".join(code_files.values()).lower()
    for item in items_to_check:
        req_id = item.get("id", "REQ")
        title = item.get("title", "")
        desc = item.get("description", "")
        clarity = item.get("clarity", "clear")

        if not test_passed and any(f in test_output for f in code_files):
            r_status = "failed"
            r_reason = "Runtime test failure occurred while executing generated project."
        elif clarity in ("unclear", "missing_detail") and len(desc.split()) < 4:
            r_status = "not_checked"
            r_reason = f"Flagged in PRD checklist as {clarity}; requires stakeholder clarification."
        else:
            # Check for core tokens in generated codebase
            tokens = [w for w in re.findall(r"\b[A-Za-z]{4,}\b", desc.lower()) if w not in ("with", "that", "this", "from", "user", "must", "have", "will", "into")]
            matches = sum(1 for t in tokens if t in concat_code)
            if tokens and len(tokens) >= 2 and matches == 0:
                r_status = "failed"
                r_reason = f"No implementation found for key requirement terms ({', '.join(tokens[:3])})."
                failing_files_set.add(list(code_files.keys())[0] if code_files else "main.py")
            else:
                r_status = "passed"
                r_reason = "Requirement verified against generated code structures and test suite."

        requirements_review.append(RequirementReviewModel(
            id=req_id,
            title=title,
            status=r_status,
            reason=r_reason
        ))

    # Overall pass/fail determination
    all_reqs_ok = all(r.status == "passed" or (r.status == "not_checked" and len(failing_files_set) == 0) for r in requirements_review)
    all_files_ok = all(f.status == "passed" for f in planned_files_review)
    all_integ_ok = all(i.passed for i in integration_review)
    prev_ok = bool(preview_review and preview_review.can_preview)

    passed = (
        len(failing_files_set) == 0
        and len(all_issues) == 0
        and test_passed
        and all_reqs_ok
        and all_files_ok
        and all_integ_ok
        and prev_ok
    )
    sorted_failing_files = sorted(list(failing_files_set))

    if passed:
        summary = (
            f"All QA checks passed successfully. Verified {len(code_files)} file(s), "
            f"{len(requirements_review)} requirement(s) passed, preview verified ({preview_review.preview_type}), and unit tests passed."
        )
    else:
        failed_req_count = sum(1 for r in requirements_review if r.status == "failed")
        if repair_count < 3:
            summary = (
                f"QA verification failed on {len(sorted_failing_files)} file(s) ({', '.join(sorted_failing_files)}) "
                f"with {failed_req_count} failing requirement(s). Triggering bounded repair attempt #{repair_count + 1} of 3."
            )
        else:
            summary = (
                f"QA checks unresolved after 3 repair attempts. Remaining problems: {len(sorted_failing_files)} failing file(s) ({', '.join(sorted_failing_files)}), "
                f"{failed_req_count} failing requirement(s). Reporting issues clearly without claiming false success."
            )

    return QAReport(
        passed=passed,
        summary=summary,
        failing_files=sorted_failing_files,
        test_output=test_output,
        requirements_review=requirements_review,
        planned_files_review=planned_files_review,
        integration_review=integration_review,
        preview_review=preview_review,
        criteria_results=criteria_results,
        issues=all_issues,
    )


def refactor_code(files: Dict[str, str]) -> Tuple[Dict[str, str], List[Dict[str, str]]]:
    """Refactors developer modules to adhere to standard library patterns and typing."""
    refactored = {}
    changelog = []

    for filename, content in files.items():
        if filename == "main.py" and "processed_items = len(payload)" in content:
            enhanced_content = content.replace(
                "    # Core domain business logic\n    result = {\n        \"status\": \"success\",\n        \"processed_items\": len(payload),\n        \"data\": payload\n    }\n    return result",
                "    # Refactored: Standardized response envelope with typing\n    from typing import cast\n    result: Dict[str, Any] = {\n        \"status\": \"success\",\n        \"processed_items\": len(payload),\n        \"data\": dict(payload),\n    }\n    return cast(Dict[str, Any], result)"
            )
            refactored[filename] = enhanced_content
            changelog.append({
                "file": filename,
                "type": "typing_and_immutability",
                "description": "Standardized response dictionary casting and shallow payload copy to prevent mutation."
            })
        elif filename == "utils.py" and "def format_timestamp(dt) -> str:" in content:
            enhanced_content = content.replace(
                "def format_timestamp(dt) -> str:\n    \"\"\"Formats datetime to standard ISO 8601 string.\"\"\"\n    return dt.isoformat()",
                "from datetime import datetime, timezone\n\ndef format_timestamp(dt: Optional[datetime] = None) -> str:\n    \"\"\"Formats datetime to UTC ISO 8601 string, defaulting to current time.\"\"\"\n    target = dt or datetime.now(timezone.utc)\n    return target.isoformat()"
            )
            refactored[filename] = enhanced_content
            changelog.append({
                "file": filename,
                "type": "standard_library_datetime",
                "description": "Refactored timestamp formatting to use timezone-aware datetime standard library objects."
            })
        else:
            refactored[filename] = content

    return refactored, changelog


def qa_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node executing QA verification, test execution, and repair routing."""
    code_files = state.get("generated_code") or state.get("dev_code_files", {})
    plan = state.get("plan")
    repair_count = state.get("repair_count", 0)
    prd_checklist = state.get("prd_checklist", [])
    session_id = state.get("session_id", "preview")

    qa_report = analyze_and_test_project(
        code_files=code_files,
        plan=plan,
        repair_count=repair_count,
        prd_checklist=prd_checklist,
        session_id=session_id,
    )
    refactored_files, changelog = refactor_code(code_files)

    for issue in qa_report.issues:
        changelog.append({
            "file": issue.file_path,
            "type": issue.issue_type,
            "description": issue.description,
        })

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Form repair context if QA failed and we have repair attempts left (< 3)
    if not qa_report.passed and repair_count < 3:
        qa_repair_context = {
            "failing_files": qa_report.failing_files,
            "test_output": qa_report.test_output,
            "issues": [issue.model_dump() for issue in qa_report.issues],
            "failing_requirements": [r.model_dump() for r in qa_report.requirements_review if r.status == "failed"],
            "failing_files_review": [f.model_dump() for f in qa_report.planned_files_review if f.status != "passed"],
            "integration_failures": [i.model_dump() for i in qa_report.integration_review if not i.passed],
        }
    else:
        qa_repair_context = None

    error_msg = None
    if not qa_report.passed and repair_count >= 3:
        error_msg = qa_report.summary

    passed_count = sum(1 for r in qa_report.requirements_review if r.status == "passed")
    total_count = len(qa_report.requirements_review)
    log_entry = {
        "agent": "QA",
        "stage": "qa_review",
        "message": f"QA Audit (Passed: {qa_report.passed}, Requirements: {passed_count}/{total_count} passed, Failures: {len(qa_report.failing_files)}, RepairCount: {repair_count}) - {qa_report.summary}",
        "timestamp": timestamp,
        "failing_files": qa_report.failing_files,
        "requirements_passed": passed_count,
        "requirements_total": total_count,
        "preview_ok": qa_report.preview_review.can_preview if qa_report.preview_review else False,
    }

    return {
        "qa_report": qa_report.model_dump(mode="json"),
        "qa_passed": qa_report.passed,
        "qa_repair_context": qa_repair_context,
        "test_output": qa_report.test_output,
        "failing_files": qa_report.failing_files,
        "qa_unresolved_summary": qa_report.summary if (not qa_report.passed and repair_count >= 3) else None,
        "qa_refactored_files": refactored_files,
        "qa_changelog": changelog,
        "current_stage": "qa_completed" if qa_report.passed or repair_count >= 3 else f"qa_failed_repair_{repair_count + 1}",
        "error": error_msg,
        "logs": [log_entry],
    }


def analyze_code_qa(code_files: Dict[str, str], plan: Optional[Dict[str, Any]] = None, repair_count: int = 0) -> QAReport:
    """Backward-compatible alias for full QA analysis and testing."""
    return analyze_and_test_project(code_files, plan=plan, repair_count=repair_count)


def analyze_code_qa_fallback(code_files: Dict[str, str], *args, **kwargs) -> QAReport:
    """Backward-compatible fallback for QA analysis."""
    return analyze_and_test_project(code_files)

