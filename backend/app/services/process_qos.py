"""实时进程的局部 HighQoS 生命周期；不修改优先级、亲和性或系统电源设置。"""
from contextlib import contextmanager
from copy import deepcopy
import os
from threading import RLock

_lock = RLock()
_users = 0
_original = None
_observation = None


def _is_windows():
    return os.name == 'nt'


def _power_api():
    import ctypes
    class State(ctypes.Structure):
        _fields_ = [('Version', ctypes.c_uint32), ('ControlMask', ctypes.c_uint32),
                    ('StateMask', ctypes.c_uint32)]
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    for name in ('GetProcessInformation', 'SetProcessInformation'):
        function = getattr(api, name)
        function.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)
        function.restype = ctypes.c_int
    return ctypes, api, State


def _read_power_state():
    ctypes, api, State = _power_api()
    value = State(1, 0, 0)
    if not api.GetProcessInformation(ctypes.c_void_p(-1), 4, ctypes.byref(value), ctypes.sizeof(value)):
        raise ctypes.WinError(ctypes.get_last_error())
    return value.Version, value.ControlMask, value.StateMask


def _write_power_state(state):
    ctypes, api, State = _power_api()
    value = State(*state)
    if not api.SetProcessInformation(ctypes.c_void_p(-1), 4, ctypes.byref(value), ctypes.sizeof(value)):
        raise ctypes.WinError(ctypes.get_last_error())


def _restore_speed(original):
    current = _read_power_state()
    desired = (current[0], (current[1] & ~1) | (original[1] & 1),
               (current[2] & ~1) | (original[2] & 1))
    _write_power_state(desired)
    restored = _read_power_state()
    if restored != desired:
        raise RuntimeError('process_qos_restore_mismatch')
    return restored


def process_qos_snapshot():
    with _lock:
        return deepcopy(_observation)


@contextmanager
def high_qos():
    global _users, _original, _observation
    with _lock:
        if _users == 0:
            supported = _is_windows()
            record = dict(pid=os.getpid(), supported=supported, before=None, applied=None, restored=None)
            _observation = record
            if supported:
                # 若上次恢复失败，保留首次原策略，下一次退出仍可重试恢复。
                if _original is None:
                    _original = _read_power_state()
                record['before'] = list(_original)
                current = _read_power_state()
                desired = (current[0], current[1] | 1, current[2] & ~1)
                try:
                    _write_power_state(desired)
                    applied = _read_power_state()
                    if applied != desired:
                        raise RuntimeError('process_qos_apply_mismatch')
                    record['applied'] = list(applied)
                except BaseException:
                    record['restored'] = list(_restore_speed(_original))
                    _original = None
                    raise
            _observation = record
        record = _observation
        _users += 1
    try:
        yield record
    finally:
        with _lock:
            _users -= 1
            if _users == 0 and _original is not None:
                restored = _restore_speed(_original)
                record['restored'] = list(restored)
                _original = None
