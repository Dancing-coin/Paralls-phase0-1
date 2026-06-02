class EventTraceService:
    def __init__(self) -> None:
        self._events: list[str] = []

    def record(self, event_name: str) -> None:
        self._events.append(event_name)

    def summary(self) -> list[str]:
        return list(self._events)
