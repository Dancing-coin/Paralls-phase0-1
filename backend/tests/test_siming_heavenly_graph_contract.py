from heavenly_graph_contract import HeavenlyGraphContract

from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_heavenly_graph_port import HeavenlyGraphPort


class TestInMemoryHeavenlyGraphContract(HeavenlyGraphContract):
    def make_graph(self) -> HeavenlyGraphPort:
        return InMemoryHeavenlyGraphAdapter()
