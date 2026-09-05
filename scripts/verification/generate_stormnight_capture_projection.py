from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.p5.stormnight_realtime_session import StormnightPlayerIntent, StormnightRealtimeSessionService
from common import repo_root, verification_dir, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("arrival", "evidence", "pursuit"), required=True)
    args = parser.parse_args()
    service = StormnightRealtimeSessionService(store=GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry()))
    response = service.handle(StormnightPlayerIntent(kind="start", request_id=f"capture:{args.stage}:start"))
    if args.stage in {"evidence", "pursuit"}:
        response = service.handle(StormnightPlayerIntent(kind="inspect", request_id=f"capture:{args.stage}:inspect"))
        response = service.handle(StormnightPlayerIntent(kind="advance", request_id=f"capture:{args.stage}:advance"))
    if args.stage == "pursuit":
        response = service.handle(StormnightPlayerIntent(kind="pursue", request_id="capture:pursuit:action"))
    if not response.accepted:
        return 1
    path = verification_dir(repo_root()) / f"stormnight-realtime-{args.stage}-projection.json"
    write_json(path, response.model_dump(mode="json"))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
