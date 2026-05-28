from typing import Protocol

from backend.handoff.models import CRMLeadPayload, LeadCreationResult


class CRMClient(Protocol):
    async def create_lead(self, payload: CRMLeadPayload) -> LeadCreationResult: ...


class PostgresCRMClient:
    async def create_lead(self, payload: CRMLeadPayload) -> LeadCreationResult:
        raise NotImplementedError
