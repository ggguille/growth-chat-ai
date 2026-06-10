import asyncio
import json
from typing import Protocol

from backend.handoff.models import CRMDeliveryError, CRMLeadPayload, LeadCreationResult


class CRMClient(Protocol):
    async def create_lead(self, payload: CRMLeadPayload) -> LeadCreationResult: ...


class PostgresCRMClient:
    async def create_lead(self, payload: CRMLeadPayload) -> LeadCreationResult:
        from backend.config import settings

        db_url = settings.checkpoint_db_url
        if not db_url:
            raise CRMDeliveryError(http_status=None, message="CHECKPOINT_DB_URL not configured")

        # Use synchronous psycopg via asyncio.to_thread — avoids ProactorEventLoop
        # incompatibility with psycopg async on Windows (same pattern as email_fallback.py).
        def _insert() -> str:
            import psycopg

            with psycopg.connect(db_url, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO leads (
                            session_id, lead_level, handoff_reason,
                            visitor_email, visitor_name, visitor_company, visitor_role,
                            problem_fit, authority_fit, company_fit, timing_fit,
                            is_consultant, referral_mentioned,
                            turn_count, signals_observed, conversation_summary
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s,
                            %s, %s::jsonb, %s
                        ) RETURNING id
                        """,
                        (
                            payload.session_id,
                            payload.lead_level,
                            payload.handoff_reason,
                            payload.contact.email,
                            payload.contact.name,
                            payload.contact.company,
                            payload.contact.role,
                            payload.problem_fit,
                            payload.authority_fit,
                            payload.company_fit,
                            payload.timing_fit,
                            payload.is_consultant,
                            payload.referral_mentioned,
                            payload.turn_count,
                            json.dumps(payload.signals_observed),
                            payload.summary,
                        ),
                    )
                    row = cur.fetchone()
            return str(row[0])

        try:
            crm_record_id = await asyncio.to_thread(_insert)
            return LeadCreationResult(crm_record_id=crm_record_id, crm_record_url="")
        except CRMDeliveryError:
            raise
        except Exception as exc:
            raise CRMDeliveryError(http_status=None, message=str(exc)) from exc
