---
name: fastapi
description: Standards for building high-performance, modular Python web APIs with FastAPI, Pydantic, and async routes.
---

# FastAPI Engineering Skill

Use this skill when developing Python REST APIs, microservices, or backend services.

## 1. Modular Application Architecture
- Initialize `app = FastAPI(title="...", version="...")`.
- Group related endpoints using `APIRouter(prefix="/...", tags=["..."])` or dedicated modules.
- Configure CORS middleware (`CORSMiddleware`) allowing appropriate origins, methods, and headers.
- If serving a web frontend alongside the API:
  - Mount static assets: `app.mount("/static", StaticFiles(directory="static"), name="static")` or `app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")`.
  - Serve root HTML via `FileResponse("frontend/index.html")` or `FileResponse("index.html")`.

## 2. Request & Response Validation with Pydantic
- Define explicit request and response models inheriting from `pydantic.BaseModel`.
- Use type hints, `Field(...)` constraints, and default values.
- Never accept unvalidated raw dictionaries or arbitrary query parameters.
- Provide descriptive HTTP status codes (`status.HTTP_201_CREATED`, `status.HTTP_204_NO_CONTENT`, etc.).

## 3. Error Handling & Resilience
- Raise `HTTPException(status_code=..., detail="...")` with informative error messages.
- Return structured error responses rather than unhandled server 500 crashes.
- Validate path parameters and query arguments cleanly.

## 4. Dependencies & Best Practices
- Use FastAPI dependency injection (`Depends`) for shared logic, authentication, or database sessions.
- Avoid global mutable state where possible; encapsulate storage in repository classes or services.
- Keep dependencies standard and minimal (`fastapi`, `uvicorn`, `pydantic`).
