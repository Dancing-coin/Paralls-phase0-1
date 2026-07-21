import asyncio
import json

import websockets


async def main() -> None:
    uri = "ws://127.0.0.1:8000/ws"
    async with websockets.connect(uri) as ws:
        intent = {
            "message_type": "player_input",
            "payload": {
                "player_id": "player",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": "char_c",
                "intent_type": "interact_intent",
                "producer_ts": 999999,
                "target_object_id": "obj_letter",
                "interaction_type": "inspect",
            },
        }
        await ws.send(json.dumps(intent))
        print("SENT interact_intent")
        try:
            for _ in range(10):
                raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                msg = json.loads(raw)
                mt = msg.get("message_type")
                payload = msg.get("payload", {})
                summary = payload.get("result_type") or payload.get("route") or payload.get("output_type") or ""
                print("RECV", mt, summary)
        except TimeoutError:
            print("TIMEOUT waiting for more messages")


asyncio.run(main())
