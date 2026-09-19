"""性能采集使用生产 QoS 生命周期，并保留真实策略读回记录。"""
from contextlib import contextmanager
from app.services.process_qos import high_qos, process_qos_snapshot


@contextmanager
def recorded_high_qos(path):
    from scripts.verification.population_godot_runner import write_json
    error = None
    try:
        with high_qos():
            yield
    except BaseException as failure:
        error = type(failure).__name__
        raise
    finally:
        if path.parent.exists():
            observation = process_qos_snapshot()
            write_json(path, dict(observation or {}, error=error))


def require_restored_qos(record):
    """原生记录只核本包拥有的 speed 位；其他策略位允许由外部改变。"""
    if (not isinstance(record, dict) or record.get('error') is not None
            or type(record.get('supported')) is not bool
            or type(record.get('pid')) is not int or record['pid'] <= 0):
        raise ValueError('process_qos_lifecycle_invalid')
    before, applied, restored = (record.get(key) for key in ('before', 'applied', 'restored'))
    if not record['supported']:
        if any(value is not None for value in (before, applied, restored)):
            raise ValueError('process_qos_lifecycle_invalid')
        return
    if any(not isinstance(value, list) or len(value) != 3
           or any(type(item) is not int or item < 0 for item in value) or value[0] != 1
           for value in (before, applied, restored)):
        raise ValueError('process_qos_lifecycle_invalid')
    if (applied[1] & 1 != 1 or applied[2] & 1 != 0
            or restored[1] & 1 != before[1] & 1 or restored[2] & 1 != before[2] & 1):
        raise ValueError('process_qos_lifecycle_invalid')
