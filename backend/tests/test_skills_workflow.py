"""Tests for TARA Skill-Aware LangGraph workflow, safe skill loader, and agent execution."""

import pytest
from pathlib import Path
from app.agents.skills_loader import (
    list_available_skills,
    load_skill,
    load_skills,
    format_skills_for_prompt,
    SKILLS_DIR,
)
from app.agents.planner import generate_plan_fallback, planner_node
from app.agents.developer import developer_node, generate_code_fallback
from app.agents.qa import qa_node
from app.graph.state import create_initial_state
from app.graph.workflow import create_tara_workflow


def test_list_available_skills():
    """Verify list_available_skills discovers trusted application skills."""
    skills = list_available_skills()
    assert "web-frontend" in skills
    assert "fastapi" in skills
    assert "database" in skills
    assert "testing" in skills


def test_safe_skill_loader_valid():
    """Verify valid skills load expected markdown content."""
    web_skill = load_skill("web-frontend")
    assert web_skill is not None
    assert "Web Frontend Engineering Skill" in web_skill
    assert "frontend/index.html" in web_skill

    fastapi_skill = load_skill("fastapi")
    assert fastapi_skill is not None
    assert "FastAPI Engineering Skill" in fastapi_skill

    db_skill = load_skill("database")
    assert db_skill is not None
    assert "Database & Persistence Engineering Skill" in db_skill

    test_skill = load_skill("testing")
    assert test_skill is not None
    assert "Testing & Quality Assurance Engineering Skill" in test_skill


def test_safe_skill_loader_security_traversal():
    """Verify loader blocks directory traversal and invalid names."""
    assert load_skill("../../main.py") is None
    assert load_skill("../..") is None
    assert load_skill("/etc/passwd") is None
    assert load_skill("C:\\Windows\\System32") is None
    assert load_skill("non_existent_skill_xyz") is None
    assert load_skill("") is None
    assert load_skill(None) is None  # type: ignore


def test_load_multiple_skills_and_format():
    """Verify loading multiple skills and prompt formatting."""
    skills = load_skills(["web-frontend", "testing", "invalid-skill"])
    assert "web-frontend" in skills
    assert "testing" in skills
    assert "invalid-skill" not in skills

    formatted = format_skills_for_prompt(skills)
    assert "### Active Engineering Skills & Best Practices:" in formatted
    assert "Skill: web-frontend" in formatted
    assert "Skill: testing" in formatted


def test_planner_skill_selection_web():
    """Verify Planner selects web-frontend, fastapi, and testing for web PRDs."""
    web_prd = """# Team Task Dashboard
    Build a modern web application for team task management.
    Requirements:
    - HTML/CSS frontend with interactive task boards.
    - REST API backend with FastAPI for creating and updating tasks.
    - SQLite database for persistent storage.
    """
    plan = generate_plan_fallback(web_prd)
    assert plan.requires_web is True
    assert "web-frontend" in plan.selected_skills
    assert "fastapi" in plan.selected_skills
    assert "testing" in plan.selected_skills
    assert "database" in plan.selected_skills

    # Verify file plan has separated frontend files
    paths = [f.path for f in plan.file_plan]
    assert "frontend/index.html" in paths
    assert "frontend/styles.css" in paths
    assert "frontend/app.js" in paths
    assert "main.py" in paths


def test_planner_skill_selection_cache():
    """Verify Planner selects database and testing without forcing web for backend service."""
    cache_prd = """# High-Performance Cache Service
    In-memory key-value cache with TTL expiration and cleanup background task.
    """
    plan = generate_plan_fallback(cache_prd)
    assert plan.requires_web is False
    assert "web-frontend" not in plan.selected_skills
    assert "database" in plan.selected_skills
    assert "testing" in plan.selected_skills

    paths = [f.path for f in plan.file_plan]
    assert not any("index.html" in p for p in paths)


def test_developer_and_qa_skill_aware_workflow():
    """Verify end-to-end flow from planning to code generation and QA verification."""
    prd_text = """# Weather Analytics Web App
    Build a responsive dashboard displaying weather telemetry.
    Requirements:
    - Interactive controls to query temperature and humidity.
    - Clean responsive visual layout.
    """
    state = create_initial_state("test-skill-workflow-session", prd_text, "Weather_PRD.md")
    
    # 1. Planner Node
    plan_out = planner_node(state)
    assert "plan" in plan_out
    assert "selected_skills" in plan_out
    assert "web-frontend" in plan_out["selected_skills"]
    state = {**state, **plan_out}  # type: ignore

    # 2. Developer Node
    dev_out = developer_node(state)
    assert "dev_code_files" in dev_out
    files = dev_out["dev_code_files"]
    assert "frontend/index.html" in files
    assert "frontend/styles.css" in files
    assert "frontend/app.js" in files
    assert "main.py" in files
    state = {**state, **dev_out}  # type: ignore

    # 3. QA Node
    qa_out = qa_node(state)
    assert "qa_report" in qa_out
    assert qa_out["qa_passed"] is True
    assert len(qa_out["qa_report"]["failing_files"]) == 0
