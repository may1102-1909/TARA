---
name: web-frontend
description: Standards and guidelines for crafting responsive, modern, connected web frontend applications with HTML5, CSS3, and JavaScript.
---

# Web Frontend Engineering Skill

Use this skill when developing browser-based interfaces, dashboards, or web applications.

## 1. Directory Structure & File Conventions
For web projects requiring frontend files:
- `frontend/index.html` (or `index.html`): Semantic HTML5 structure.
- `frontend/styles.css` (or `static/styles.css`): Modern responsive CSS styles.
- `frontend/app.js` (or `static/app.js`): Client-side JavaScript application logic.
- Ensure all stylesheet `<link rel="stylesheet" href="...">` and script `<script src="...">` tags match the exact relative or mounted paths.

## 2. HTML5 Semantic Architecture
- Include valid `<!doctype html>`, `<html lang="en">`, `<head>`, and `<body>`.
- Provide meaningful `<title>` and `<meta name="viewport" content="width=device-width, initial-scale=1.0">`.
- Use semantic tags: `<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, `<aside>`, `<footer>`.
- Assign clear `id` and `class` attributes to interactive elements (buttons, inputs, tables, cards).

## 3. CSS Modern Aesthetics & Layout
- Use CSS variables (`:root { ... }`) for color schemes, typography, and spacing tokens.
- Implement responsive layouts using CSS Flexbox and Grid.
- Provide clear visual hierarchy, accessible contrast ratios, and responsive breakpoints (`@media (max-width: 768px)`).
- Include subtle transitions (`transition: all 0.2s ease;`) and interactive `:hover` / `:focus` states.

## 4. Client-side JavaScript Implementation
- Organize logic cleanly: state management, DOM event listeners, and API/render functions.
- Every button, input, or control must have real event handlers (`addEventListener`).
- Prohibit dead buttons or dummy placeholder alerts.
- Render dynamic list items, status badges, and feedback messages cleanly to the DOM.
- Sanitize dynamic user inputs using `textContent` or proper encoding to avoid XSS.
