import asyncio
import math
from time import perf_counter
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('kind', ['character', 'siming'])
def test_cognition_poll_is_bounded_with_coarse_clock_and_ready_callbacks(monkeypatch, kind):
    from app import main
    async def run():
        loop = asyncio.get_running_loop()
        resolution = .015625
        original_time = loop.time
        monkeypatch.setattr(loop, '_clock_resolution', resolution)
        monkeypatch.setattr(loop, 'time', lambda: math.floor(original_time()/resolution)*resolution)
        polls = 0
        alive = True
        async def poll():
            nonlocal polls
            polls += 1
        async def close(): pass
        monkeypatch.setattr(main, f'_{kind}_cognition_driver', SimpleNamespace(poll=poll, close=close))
        def ready():
            if alive:
                loop.call_soon(ready)
        loop.call_soon(ready)
        task = asyncio.create_task(getattr(main, f'_run_{kind}_cognition')())
        try:
            started = perf_counter()
            while perf_counter()-started < .15:
                await asyncio.sleep(.03)
            assert 1 <= polls < 100, polls
        finally:
            alive = False
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    asyncio.run(run())
