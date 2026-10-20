---
name: testing
description: Standards for rigorous test suites, automated test execution, TestClient assertions, and edge case coverage.
---

# Testing & Quality Assurance Engineering Skill

Use this skill when designing, generating, or validating test suites.

## 1. Test Architecture & Conventions
- Use standard Python testing frameworks: `unittest` or `pytest`.
- For FastAPI applications, use `starlette.testclient.TestClient(app)` to exercise endpoints without binding physical networking ports.
- Structure tests into logical test cases: unit tests for core logic, integration tests for API endpoints.

## 2. Test Coverage & Edge Cases
- Test the happy path with valid input payloads.
- Test validation failures (invalid types, missing required fields, boundary violations) verifying 422 or 400 responses.
- Test error paths (resource not found 404, conflicts 409).
- Test state consistency across sequential calls (e.g., create -> get -> update -> delete -> get 404).

## 3. Isolation & Determinism
- Use isolated temporary directories or in-memory databases (`:memory:`) so tests do not pollute host storage.
- Never rely on hardcoded clock times or external internet services; mock external dependencies if necessary.
- Assert explicit response structures, status codes, and JSON schemas.
