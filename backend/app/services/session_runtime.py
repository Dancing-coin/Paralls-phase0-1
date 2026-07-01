from app.services.session_input_router import SessionInputRouter


# Compatibility alias for older imports. New code should use SessionInputRouter.
SessionRuntime = SessionInputRouter

__all__ = ["SessionInputRouter", "SessionRuntime"]
