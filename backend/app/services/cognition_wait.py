"""普通感知事实已提交后的临时等待；不产生 durable delivery 声明。"""
import asyncio
from threading import Event
from time import monotonic


def _complete(request, gateway, cancelled, emit):
    try:
        return gateway.complete_prepared_request(request), None
    except Exception as error:
        return None, error


async def finish_cognition_wait(*, runtime, advance, owner_call, slots, connection_current=None, on_completed=None):
    turn_id = advance.next_job.turn_id if advance.next_job else None
    slot = None
    cancelled = Event()
    try:
        while advance.status == 'pending':
            job = advance.next_job
            while slot is None:
                if monotonic() >= job.deadline_monotonic:
                    return await owner_call(lambda: runtime.cancel_cognition_turn(turn_id, reason='deadline_expired'))
                slot = slots.acquire()
                if slot is None:
                    await asyncio.sleep(.02)
            def prepare_gateway():
                if connection_current is not None and not connection_current():
                    return None
                return runtime._l2._gateway if job.task_kind == 'l2_reasoning' else runtime._l3._gateway
            gateway = await owner_call(prepare_gateway)
            if gateway is None:
                return await owner_call(lambda: runtime.cancel_cognition_turn(turn_id, reason='connection_stale'))
            future = slot.submit(job.request_json, gateway, cancelled, None, runner=_complete)
            try:
                output, error = await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)),
                    timeout=max(0., job.deadline_monotonic-monotonic()))
            except TimeoutError:
                return await owner_call(lambda: runtime.cancel_cognition_turn(turn_id, reason='deadline_expired'))
            else:
                def commit():
                    if connection_current is not None and not connection_current():
                        return runtime.cancel_cognition_turn(turn_id, reason='connection_stale')
                    result = runtime.commit_cognition_result(job, output=output, error=error)
                    if result.status == 'completed' and on_completed is not None:
                        on_completed(result)
                    return result
                advance = await owner_call(commit)
        return advance
    finally:
        cancelled.set()
        try:
            if turn_id is not None:
                # 反复取消不能遗失已在 owner 排队的收口；不撤销感知前缀。
                cleanup = asyncio.create_task(owner_call(lambda: runtime.cancel_cognition_turn(turn_id, reason='transport_finished')))
                while not cleanup.done():
                    try:
                        await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        continue
                cleanup.result()
        finally:
            if slot is not None:
                slot.close()
