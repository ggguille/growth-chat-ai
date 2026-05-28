from backend.handoff.models import HandoffRequest


async def dispatch_handoff(request: HandoffRequest) -> None:
    raise NotImplementedError
