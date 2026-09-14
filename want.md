# What Antigravity Needs From You (TARA Roadmap Requirements)

To continue transforming **TARA** into an enterprise-grade AI Software Engineering Web IDE, here is the list of inputs, preferences, and credentials that will help us build the next milestones:

---

## 1. Credentials for Upcoming Steps (When Ready)

| Requirement | Purpose | How to Provide |
|---|---|---|
| **GitHub Personal Access Token (PAT)** | To implement **Step 5: Automated GitHub PR & Repository Creation** (FR-21 to FR-23) so TARA can directly push hardened code and open PRs. | Add `GITHUB_TOKEN=ghp_...` to your `.env` (with `repo` scope). |
| **Target GitHub Username / Org** | Default organization or account where generated repositories will be initialized. | Mention in conversation or set `GITHUB_USER=...` in `.env`. |

---

## 2. Web IDE & Monaco Customization Preferences

1. **Default Diff View Preference**:
   - Would you prefer Monaco's diff viewer to default to **Side-by-Side (Split View)** or **Inline (Unified Git-style View)**? *(We have added a toggle button so you can switch at any time).*
2. **Editor Live Saving & Sync**:
   - When you edit code in the Monaco Editor, should manual edits immediately override AI code when running in the sandbox? *(Currently enabled: any manual edits you make in Monaco are saved live to the sandbox workspace).*
3. **One-Click Terminal Actions**:
   - What quick action buttons would you like in the Web IDE terminal header?
     - `▶️ Run main.py` (Currently active)
     - `🧪 Run pytest tests`
     - `🛡️ Re-scan Bandit SAST`
     - `📦 pip install <package>`

---

## 3. Real PRD Test Documents

- If you have a specific real-world `.pdf` or `.md` specification you want to test (e.g. an e-commerce API, microservices auth system, or data pipeline), drop it into the Web IDE to benchmark the CEO, Developer, QA, and Security Officer.

---

## 4. Cloud Quota & API Health

- **E2B API Credits**: Ensure your [E2B Dashboard](https://e2b.dev) has active credits for Tier 1 cloud microVM execution.
- **Gemini Free Tier Quota**: If you have multiple Gemini API keys or paid tier access, let us know if you want higher rate limits for complex 10+ file architectures.
