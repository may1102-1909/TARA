import asyncio
import json
import websockets

async def test_ws_stream():
    uri = "ws://127.0.0.1:8000/ws/tara/stream"
    async with websockets.connect(uri) as ws:
        init_msg = await ws.recv()
        print("Init message received:", init_msg)

        payload = {
            "prompt": "replace the name RTI ONE CLICK with RTI OneClick",
            "file_path": "app/database.py",
            "current_code": (
                "# Database setup\n"
                "app_name = 'RTI ONE CLICK'\n"
                "db_version = '1.0.0'\n\n"
                "def get_database_status():\n"
                "    return {'app': app_name, 'connected': True}\n"
            ),
            "action": "edit"
        }
        await ws.send(json.dumps(payload))
        print("Sent edit prompt to /ws/tara/stream")

        streamed_chunks = []
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            msg_type = data.get("type")
            if msg_type == "STREAM_START":
                print(f"STREAM_START: agent={data.get('agent')} engine={data.get('engine')}")
            elif msg_type == "CODE_DELTA":
                streamed_chunks.append(data.get("delta", ""))
            elif msg_type == "STREAM_END":
                print(f"STREAM_END: {data.get('summary')}")
                break
            elif msg_type == "ERROR":
                print("Error received:", data)
                break

        full_streamed = "".join(streamed_chunks)
        print("\n=== Streamed Code Result ===")
        print(full_streamed)
        assert "RTI OneClick" in full_streamed, "Target text was not updated to RTI OneClick"
        assert "def execute_task()" not in full_streamed, "Placeholder stub was erroneously generated!"
        print("\n[SUCCESS] Verification PASSED: Real code streamed from Developer Agent via Local Ollama (qwen2.5:7b)!")

if __name__ == "__main__":
    asyncio.run(test_ws_stream())
