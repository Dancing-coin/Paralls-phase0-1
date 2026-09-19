import os
from pathlib import Path
import subprocess
import sys

import pytest


def test_cold_import_does_not_open_archive_and_startup_opens_it_once_on_owner(tmp_path: Path):
    code = '''
from threading import get_ident
from fastapi.testclient import TestClient
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.world_runtime.storage_lease import RuntimeStorageLease
opened = []
sessions = []
original = SQLiteHeavenlyGraphAdapter.__init__
original_session = CharacterAgentSessionStore.__init__
def observe(self, *args, **kwargs):
    opened.append(get_ident())
    original(self, *args, **kwargs)
SQLiteHeavenlyGraphAdapter.__init__ = observe
def observe_session(self, *args, **kwargs):
    original_session(self, *args, **kwargs)
    sessions.append((get_ident(), self._connection))
CharacterAgentSessionStore.__init__ = observe_session
from app import main
assert opened == [] and sessions == [], "main import opened the durable archive"
with TestClient(main.component_app) as client:
    assert client.get('/health').status_code == 200
    assert len(opened) == 1, opened
    assert opened[0] != get_ident(), "archive opened outside runtime owner"
    assert len(sessions) == 1 and sessions[0][0] == opened[0]
    try:
        with RuntimeStorageLease(main.settings.heavenly_graph_path):
            pass
    except RuntimeError as error:
        assert str(error).startswith('runtime_storage_in_use:')
    else:
        raise AssertionError('idle live service did not hold archive lease')
import sqlite3
try:
    sessions[0][1].execute('SELECT 1')
except sqlite3.ProgrammingError:
    pass
else:
    raise AssertionError('shutdown left the session database open')
with RuntimeStorageLease(main.settings.heavenly_graph_path):
    pass
'''
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]),
               PARALLS_HEAVENLY_GRAPH_PATH=str(tmp_path / "graph.db"),
               CHARACTER_MODEL_PROVIDER_KIND="local", SIMING_LLM_MODE="disabled")
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stderr


def _cold_python(code, tmp_path):
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(root / 'backend'), str(root / 'scripts/verification'))),
               PARALLS_HEAVENLY_GRAPH_PATH=str(tmp_path / 'cold.sqlite3'),
               CHARACTER_MODEL_PROVIDER_KIND='local', SIMING_LLM_MODE='disabled')
    result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('entry', ['seed', 'cohort', 'owner_verification'])
def test_independent_population_fixture_and_verification_cold_entry(entry, tmp_path):
    code = '''
from app import main
assert 'character_agent_runtime' not in vars(main)
'''
    if entry == 'owner_verification':
        code += '''
from verify_siming_population_domain_owner_adaptation import _runtime_owner_ids
ids, shares, contracts = _runtime_owner_ids()
assert len(ids) == 4 and shares and contracts
'''
    else:
        fixture = 'SimingLedPopulationFixture' if entry == 'seed' else 'ThreeActorCohortContinuityFixture'
        code += f'''
from app.population_continuity.vertical import {fixture}
evidence = {fixture}.create().run()
assert evidence['activation']['actual_player_input_path']
assert evidence['activation']['same_character_identity']
'''
    code += '''
import sqlite3
try:
    main.heavenly_graph._connection.execute('SELECT 1')
except sqlite3.ProgrammingError:
    pass
else:
    raise AssertionError('offline caller left its graph connection open')
'''
    _cold_python(code, tmp_path)


@pytest.mark.parametrize('failure_stage', ['after_graph', 'rehydrate', 'after_runtime', 'cleanup_failure', 'session_cleanup_failure'])
def test_failed_local_construction_closes_connections_before_releasing_lease(failure_stage, tmp_path):
    _cold_python('''
import asyncio
import sqlite3
from pathlib import Path
from app import main
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.world_runtime.storage_lease import RuntimeStorageLease
opened = []
graph_init = main.SQLiteHeavenlyGraphAdapter.__init__
session_init = CharacterAgentSessionStore.__init__
def observe_graph(self, *args, **kwargs):
    graph_init(self, *args, **kwargs)
    opened.append(self._connection)
def observe_session(self, *args, **kwargs):
    session_init(self, *args, **kwargs)
    if self._connection is not None:
        opened.append(self._connection)
main.SQLiteHeavenlyGraphAdapter.__init__ = observe_graph
CharacterAgentSessionStore.__init__ = observe_session
def fail(*args, **kwargs):
    raise ValueError('injected_local_construction_failure')
stage = ''' + repr(failure_stage) + '''
if stage == 'after_graph':
    main.CharacterMemoryStoreRouter = fail
elif stage in {'rehydrate', 'session_cleanup_failure'}:
    main.CharacterAgentRuntime._rehydrate_graph_continuity = fail
else:
    main.build_siming_llm_provider = fail
graph_close = main.SQLiteHeavenlyGraphAdapter.close
session_close = CharacterAgentSessionStore.close
if stage == 'cleanup_failure':
    main.SQLiteHeavenlyGraphAdapter.close = fail
if stage == 'session_cleanup_failure':
    CharacterAgentSessionStore.close = fail
async def start():
    try:
        await main._start_population_runtime_on_startup()
    except ValueError:
        pass
    else:
        raise AssertionError('injected startup unexpectedly succeeded')
asyncio.run(start())
assert main.get_population_runtime_failure() is not None
assert len(opened) == (1 if stage == 'after_graph' else 2)
if stage in {'cleanup_failure', 'session_cleanup_failure'}:
    assert main.runtime_execution is not None
    assert main.health()['status'] == 'unhealthy'
    try:
        with RuntimeStorageLease(main.settings.heavenly_graph_path):
            pass
    except RuntimeError:
        pass
    else:
        raise AssertionError('lease released while local graph cleanup still failed')
    main.SQLiteHeavenlyGraphAdapter.close = graph_close
    CharacterAgentSessionStore.close = session_close
    main.close_runtime_resources()
else:
    assert main.runtime_execution is None
for connection in opened:
    try:
        connection.execute('SELECT 1')
    except sqlite3.ProgrammingError:
        pass
    else:
        raise AssertionError('failed constructor retained a live SQLite connection')
path = Path(main.settings.heavenly_graph_path)
# 保留 failure traceback，仍须在 Windows 上允许重命名所有已打开的数据库。
for database in (path, path.parent / (path.name + '.character-agent') / 'character_sessions.sqlite3'):
    if database.exists():
        moved = database.with_suffix('.moved')
        database.rename(moved)
        moved.rename(database)
with RuntimeStorageLease(path):
    pass
''', tmp_path)
