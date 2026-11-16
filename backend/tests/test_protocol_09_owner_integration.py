import json
from pathlib import Path
import subprocess
import sys

from scripts.verification.population_godot_runner import child_environment


def test_proposal_executes_through_production_owner_and_lifespan(tmp_path):
    actors = ["char_a", "char_b", "char_c", *[f"resident_{i:05d}" for i in range(97)]]
    (tmp_path / "roster.json").write_text(json.dumps({"actor_ids": actors}), encoding="utf-8")
    code = '''
import asyncio, sys
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from scripts.verification.population_mixed_backend import configure
sys.path.insert(0, 'backend/tests')
from test_siming_event_producer import make_output

async def run():
    with ExitStack() as stack:
        main, _, _ = configure(Path(sys.argv[1]), stack, mode='one_x', provider_mode='local_probe')
        stack.enter_context(patch.object(main, 'start_population_runtime', lambda: None))
        async with main.component_app.router.lifespan_context(main.component_app):
            def publish():
                runtime = main.siming_event_pipeline._runtime
                event = main.siming_event_pipeline._producer.emit_environment_proposal(make_output())
                return event.payload['proposal_id']
            proposal_id = await asyncio.wrap_future(main.runtime_execution.submit(publish))
            def state():
                events = main.authority_event_bus.list_events()
                return (main.siming_event_pipeline._runtime.proposal_tracker.status(proposal_id),
                        [event.event_type for event in events],
                        main.esm_service.get_environment_field('room_demo', 'zone_focus').light_level)
            for _ in range(250):
                status, types, light = await asyncio.wrap_future(main.runtime_execution.submit(state))
                if status in {'executed', 'aborted'}:
                    break
                await asyncio.sleep(.02)
            assert status == 'executed', (status, types)
            for expected in ('siming.environment_proposal', 'esm.feasibility_response',
                             'siming.environment_request', 'esm.execution_confirmation', 'esm_result_event'):
                assert expected in types, (expected, types)
            assert light == 'low'
            assert main.get_population_runtime_failure() is None

asyncio.run(run())
'''
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], cwd=Path(__file__).resolve().parents[2],
        env=child_environment(), capture_output=True, text=True, encoding="utf-8", timeout=25,
    )
    assert result.returncode == 0, result.stderr
