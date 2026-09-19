import asyncio
from app.services.cognition_output_route import CognitionOrigin, CognitionOutputRoutes, CognitionOutputSink


def test_origin_is_exact_bounded_and_removed_on_disconnect():
    now = [1.]
    routes = CognitionOutputRoutes(capacity=2, clock=lambda: now[0])
    a, b = CognitionOrigin('a', ('session-a', 1, 10)), CognitionOrigin('b', ('session-b', 1, 10))
    routes.remember('one', a, 10)
    routes.remember('one', b, 20)
    assert routes.resolve('one') == a
    assert routes.resolve('unknown') is None
    routes.remember('two', b, 10)
    routes.remember('three', b, 10)
    assert routes.resolve('one') is None
    routes.disconnect('b')
    assert not routes.sources
    routes.remember('four', a, 2)
    now[0] = 2
    assert routes.resolve('four') is None


def test_sink_capacity_includes_delivery_until_completion_and_close_drops():
    async def run():
        values = []
        sink = CognitionOutputSink(deliver=lambda value, done, closed: values.append((value, done, closed)), capacity=1)
        payload = {'value': [1]}
        assert sink.post(payload)
        payload['value'].append(2)
        await asyncio.sleep(0)
        assert values[0][0] == {'value':[1]}
        assert not sink.post(payload)
        values[0][1]()
        assert sink.post(payload)
        sink.close()
        await asyncio.sleep(0)
        assert len(values) == 2 and values[1][2] and sink.pending == 1
        values[1][1]()
        assert sink.pending == 0
        assert not sink.post(payload)
    asyncio.run(run())


def test_disconnect_keeps_accepted_output_visible_until_terminal_completion():
    async def run():
        accepted = []
        routes = CognitionOutputRoutes()
        sink = CognitionOutputSink(deliver=lambda payload, done, closed: accepted.append((done, closed)))
        routes.connections['original'] = sink
        assert sink.post({'child_key': 'one'})
        routes.disconnect('original')
        assert sum(item.pending for item in routes.connections.values()) == 1
        await asyncio.sleep(0)
        assert accepted[0][1] is True
        assert sum(item.pending for item in routes.connections.values()) == 1
        accepted[0][0]()
        routes.release('original', sink)
        assert not routes.connections
    asyncio.run(run())
