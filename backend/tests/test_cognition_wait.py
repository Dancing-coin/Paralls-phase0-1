import asyncio
from threading import Event, get_ident

import pytest

from app.services.dialogue_continuation import DialogueProviderSlots
from app.services.cognition_wait import finish_cognition_wait
from test_cognition_completion_revision import runtime, perceived, finish


def test_wait_uses_shared_worker_and_preserves_original_result():
    async def run():
        rt, sync = runtime(), runtime()
        expected, _ = finish(sync, sync.prepare_cognition_job(source_kind='ingest_character_perceived_event', payload=perceived()))
        owner = get_ident()
        threads = []
        gateway = rt._l2._gateway
        original = gateway.complete_prepared_request
        def complete(request):
            threads.append(get_ident())
            return original(request)
        gateway.complete_prepared_request = complete
        async def owner_call(command):
            return command()
        slots = DialogueProviderSlots()
        try:
            advance = rt.prepare_cognition_job(source_kind='ingest_character_perceived_event', payload=perceived())
            result = await finish_cognition_wait(runtime=rt, advance=advance, owner_call=owner_call, slots=slots)
            assert result.status == 'completed'
            assert result.result == expected
            assert threads and all(thread != owner for thread in threads)
            assert rt.pending_cognition_jobs() == ()
        finally:
            slots._executor.shutdown(wait=True)
    asyncio.run(run())


def test_cancel_keeps_perception_and_rejects_late_completion_without_freeing_busy_slot():
    async def run():
        rt = runtime()
        started, release = Event(), Event()
        gateway = rt._l2._gateway
        original = gateway.complete_prepared_request
        def complete(request):
            started.set()
            assert release.wait(5)
            return original(request)
        gateway.complete_prepared_request = complete
        async def owner_call(command):
            return command()
        slots = DialogueProviderSlots()
        held = []
        try:
            advance = rt.prepare_cognition_job(source_kind='ingest_character_perceived_event', payload=perceived())
            job = advance.next_job
            before = list(rt._session_store.list_events('char_a'))
            task = asyncio.create_task(finish_cognition_wait(runtime=rt, advance=advance, owner_call=owner_call, slots=slots))
            for _ in range(200):
                if started.is_set():
                    break
                await asyncio.sleep(.005)
            assert started.is_set()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert rt.pending_cognition_jobs() == ()
            assert list(rt._session_store.list_events('char_a')) == before
            for _ in range(3):
                held.append(slots.acquire())
            assert all(held) and slots.acquire() is None
            release.set()
            output = original(job.request_json)
            assert rt.commit_cognition_result(job, output=output).status == 'zero_write'
            assert list(rt._session_store.list_events('char_a')) == before
        finally:
            release.set()
            for slot in held:
                if slot:
                    slot.close()
            slots._executor.shutdown(wait=True)
    asyncio.run(run())


def test_cancel_while_waiting_for_shared_capacity_cleans_only_its_turn():
    async def run():
        rt = runtime()
        async def owner_call(command):
            return command()
        slots = DialogueProviderSlots()
        held = [slots.acquire() for _ in range(4)]
        try:
            advance = rt.prepare_cognition_job(source_kind='ingest_character_perceived_event', payload=perceived())
            other = rt.prepare_cognition_job(source_kind='ingest_character_perceived_event', payload=perceived('char_b'))
            before = rt._session_store.list_all_events()
            task = asyncio.create_task(finish_cognition_wait(runtime=rt, advance=advance, owner_call=owner_call, slots=slots))
            await asyncio.sleep(.02)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert rt.pending_cognition_jobs() == (other.next_job,)
            assert rt._session_store.list_all_events() == before
            assert rt._l2._gateway.requests == []
            rt.cancel_cognition_turn(other.next_job.turn_id)
        finally:
            for slot in held:
                slot.close()
            slots._executor.shutdown(wait=True)
    asyncio.run(run())

def test_provider_timeout_error_uses_original_fallback_not_wait_deadline():
    async def run():
        rt, sync = runtime(), runtime()
        def fail(request):
            raise TimeoutError('provider timeout')
        rt._l2._gateway.complete_prepared_request = fail
        sync._l2._gateway.complete_prepared_request = fail
        expected = sync.ingest_character_perceived_event(perceived())
        async def owner_call(command):
            return command()
        slots = DialogueProviderSlots()
        try:
            advance = rt.prepare_cognition_job(source_kind='ingest_character_perceived_event', payload=perceived())
            result = await finish_cognition_wait(runtime=rt, advance=advance, owner_call=owner_call, slots=slots)
            assert result.status == 'completed'
            assert result.result == expected
        finally:
            slots._executor.shutdown(wait=True)
    asyncio.run(run())


@pytest.mark.parametrize('revoke_during_wait', [False, True])
def test_connection_fence_rejects_prepare_or_late_provider_result(revoke_during_wait):
    async def run():
        rt = runtime()
        started, release = Event(), Event()
        current = [revoke_during_wait]
        gateway = rt._l2._gateway
        original = gateway.complete_prepared_request
        def complete(request):
            started.set()
            assert release.wait(5)
            return original(request)
        gateway.complete_prepared_request = complete
        async def owner_call(command): return command()
        slots = DialogueProviderSlots()
        try:
            advance = rt.prepare_cognition_job(source_kind='ingest_character_perceived_event', payload=perceived())
            before = rt._session_store.list_events('char_a')
            task = asyncio.create_task(finish_cognition_wait(runtime=rt, advance=advance,
                owner_call=owner_call, slots=slots, connection_current=lambda: current[0]))
            if revoke_during_wait:
                for _ in range(100):
                    if started.is_set(): break
                    await asyncio.sleep(.02)
                assert started.is_set()
                current[0] = False
            release.set()
            result = await task
            assert result.status == 'requeued'
            assert result.reason == 'connection_stale'
            assert rt._session_store.list_events('char_a') == before
            assert not rt.pending_cognition_jobs()
            assert started.is_set() == revoke_during_wait
        finally:
            release.set()
            slots._executor.shutdown(wait=True)
    asyncio.run(run())
