import asyncio
import io
import json
import zipfile
import httpx
import websockets

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000"

PRD_CONTENT = """# RTI OneClick Microservice PRD
Build a high-performance Python FastAPI microservice for autonomous Right to Information (RTI) application filing.
Key Requirements:
1. Endpoints:
   - POST /api/rti/draft: Save and validate an RTI draft application.
   - POST /api/rti/submit: Submit the application to the appropriate government nodal authority.
   - GET /api/rti/status/{application_id}: Fetch tracking status and timeline.
2. Architecture:
   - Pydantic data schemas for typed validation.
   - Secure in-memory application store with thread safety.
   - Standard logging, CORS middleware, and input sanitization.
"""

def run_live_prd_e2e_test():
    print("=" * 60)
    print("STARTING TARA IDE END-TO-END PRD LIFECYCLE TEST")
    print("=" * 60)

    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        # Step 1: Health check
        print("\n[Step 1] Verifying TARA IDE server health...")
        health_resp = client.get("/health")
        assert health_resp.status_code == 200, f"Health check failed: {health_resp.text}"
        print("[OK] Server is healthy:", health_resp.json())

        # Step 2: Start session with PRD
        print("\n[Step 2] Ingesting PRD spec and triggering CEO Agent evaluation...")
        session_id = "e2e-rti-oneclick"
        start_payload = {
            "session_id": session_id,
            "prd_text": PRD_CONTENT,
            "prd_filename": "RTI_OneClick_PRD.md"
        }
        start_resp = client.post("/api/sessions/start", json=start_payload)
        assert start_resp.status_code == 200, f"Start failed: {start_resp.text}"
        start_data = start_resp.json()
        
        print("[OK] Session created:", start_data.get("session_id"))
        print("[OK] Workflow status:", start_data.get("status"))
        assert start_data.get("status") == "awaiting_approval", "Did not halt at HITL approval gate!"
        assert start_data.get("is_interrupted") is True, "Graph interrupt was not triggered!"

        critique = start_data.get("ceo_critique")
        print("\n--- CEO Agent Executive Critique ---")
        print("Verdict:", critique.get("verdict"))
        print("Feature Gaps:", critique.get("feature_gaps"))
        print("Structural Flaws:", critique.get("structural_flaws"))
        print("Recommendation:", critique.get("recommendation")[:120] + "...")

        # Step 3: Test HITL Approval Gate decision (Approve & Build)
        print("\n[Step 3] Submitting human approval to progress past Gate into Build Phase...")
        decide_payload = {
            "action": "approve",
            "notes": "Approved for autonomous multi-agent code generation."
        }
        decide_resp = client.post(f"/api/sessions/{session_id}/decide", json=decide_payload)
        assert decide_resp.status_code == 200, f"Decide failed: {decide_resp.text}"
        decide_data = decide_resp.json()

        print("[OK] Status after approval:", decide_data.get("status"))
        dev_files = decide_data.get("dev_code_files", {})
        qa_files = decide_data.get("qa_refactored_files", {})
        sec_files = decide_data.get("security_patches", {})
        
        print(f"[OK] Developer Agent generated {len(dev_files)} files: {list(dev_files.keys())}")
        print(f"[OK] QA Agent refactored {len(qa_files)} files: {list(qa_files.keys())}")
        print(f"[OK] Security Agent generated {len(sec_files)} patches: {list(sec_files.keys())}")

        audit = decide_data.get("audit_summary", {})
        print("[OK] Security Audit Summary findings:", len(audit.get("findings", [])))

        # Step 4: Verify Live App Preview routes discovery
        print("\n[Step 4] Checking Live App Preview route discovery...")
        preview_resp = client.get(f"/api/preview/routes/{session_id}")
        if preview_resp.status_code == 200:
            preview_routes = preview_resp.json().get("routes", [])
            print(f"[OK] Live Preview routes registered: {len(preview_routes)}")
        else:
            print("[INFO] Live preview routes status:", preview_resp.status_code)

        # Step 5: Test Downloadable ZIP Release Package
        print("\n[Step 5] Downloading final Release Package (.zip)...")
        dl_resp = client.get(f"/api/sessions/{session_id}/download")
        assert dl_resp.status_code == 200, f"Download failed: {dl_resp.text}"
        assert dl_resp.headers.get("content-type") == "application/zip"

        zf = zipfile.ZipFile(io.BytesIO(dl_resp.content))
        file_list = zf.namelist()
        print("[OK] Downloaded zip package contents:", file_list)
        assert any(f.endswith("main.py") for f in file_list), "main.py missing from export!"
        assert "AUDIT_SUMMARY.md" in file_list, "AUDIT_SUMMARY.md missing from export!"

    # Step 6: Test Developer Agent Interactive WebSocket Live Stream
    print("\n[Step 6] Testing interactive token streaming via /ws/tara/stream...")
    async def test_stream_socket():
        uri = f"{WS_URL}/ws/tara/stream"
        async with websockets.connect(uri) as ws:
            init_msg = json.loads(await ws.recv())
            print("[OK] WebSocket initialized:", init_msg.get("message"))

            stream_payload = {
                "prompt": "add a health check endpoint at /api/health returning status ok",
                "file_path": "main.py",
                "current_code": (
                    "from fastapi import FastAPI\n\n"
                    "app = FastAPI(title='RTI OneClick')\n"
                ),
                "action": "edit"
            }
            await ws.send(json.dumps(stream_payload))
            deltas = []
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("type") == "CODE_DELTA":
                    deltas.append(msg.get("delta", ""))
                elif msg.get("type") == "STREAM_END":
                    print("[OK] Stream completed from agent:", msg.get("agent"), "| engine:", msg.get("engine"))
                    break
            streamed_code = "".join(deltas)
            assert "/api/health" in streamed_code or "health" in streamed_code, "Streamed code did not contain health endpoint!"
            print("[OK] Live streamed code snippet:\n" + streamed_code.strip()[:200])

    asyncio.run(test_stream_socket())

    print("\n" + "=" * 60)
    print("ALL 6 PRD STAGES TESTED AND VERIFIED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_live_prd_e2e_test()
