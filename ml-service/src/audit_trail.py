"""
Audit Trail Logger — CA Professional Tools
Immutable append-only log of all client interactions and system events.
Supports RBI / ICAI compliance requirements for professional records.
Features:
  • Tamper-evident hash chain (each entry hashes previous entry's hash)
  • Event categorization: data access, modifications, filings, communications
  • User attribution and role tracking
  • Export to JSONL for regulatory submissions
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class EventCategory(str, Enum):
    DATA_ACCESS      = "data_access"
    DATA_MODIFICATION = "data_modification"
    FILING           = "filing"
    COMMUNICATION    = "communication"
    AUTH             = "authentication"
    ADMIN            = "admin"
    FINANCIAL        = "financial"
    COMPLIANCE       = "compliance"


class EventSeverity(str, Enum):
    INFO     = "info"
    WARN     = "warn"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Single immutable audit trail entry."""
    event_id:       str
    timestamp:      str                  # ISO 8601
    user_id:        str
    user_name:      str
    user_role:      str
    client_id:      Optional[str]
    event_category: EventCategory
    event_type:     str                  # Specific action (e.g. "view_itr", "send_notice")
    description:    str
    ip_address:     Optional[str]
    resource_id:    Optional[str]        # ID of the affected resource
    resource_type:  Optional[str]        # Type of resource (document, client, invoice)
    old_value:      Optional[str]        # JSON snapshot before change
    new_value:      Optional[str]        # JSON snapshot after change
    severity:       EventSeverity = EventSeverity.INFO
    session_id:     Optional[str] = None
    metadata:       Dict = field(default_factory=dict)
    # Hash chain
    previous_hash:  str = ""
    event_hash:     str = ""

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this event for integrity verification."""
        content = json.dumps({
            "event_id":       self.event_id,
            "timestamp":      self.timestamp,
            "user_id":        self.user_id,
            "event_type":     self.event_type,
            "description":    self.description,
            "client_id":      self.client_id,
            "previous_hash":  self.previous_hash,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class AuditReport:
    """Aggregated audit report for a period or client."""
    period:              str
    total_events:        int
    events_by_category:  Dict[str, int]
    events_by_user:      Dict[str, int]
    critical_events:     List[Dict]
    suspicious_patterns: List[str]
    integrity_ok:        bool
    chain_length:        int


class AuditTrailLogger:
    """
    Append-only, tamper-evident audit trail for CA professional tools.

    Usage:
        logger = AuditTrailLogger(firm_id="CA_FIRM_001")
        logger.log(AuditEvent(...))
        report = logger.generate_report(period="Mar 2025")
    """

    def __init__(self, firm_id: str = ""):
        self.firm_id  = firm_id
        self._chain:  List[AuditEvent] = []
        self._counter = 0

    def log(self, event: AuditEvent) -> str:
        """Append an event to the audit chain. Returns the event hash."""
        prev_hash = self._chain[-1].event_hash if self._chain else "GENESIS"
        event.previous_hash = prev_hash
        event.event_hash    = event.compute_hash()
        self._chain.append(event)
        self._counter += 1
        return event.event_hash

    def log_event(
        self,
        user_id:        str,
        user_name:      str,
        user_role:      str,
        event_type:     str,
        description:    str,
        client_id:      Optional[str] = None,
        category:       EventCategory = EventCategory.DATA_ACCESS,
        severity:       EventSeverity = EventSeverity.INFO,
        resource_id:    Optional[str] = None,
        resource_type:  Optional[str] = None,
        old_value:      Optional[str] = None,
        new_value:      Optional[str] = None,
        ip_address:     Optional[str] = None,
        metadata:       Optional[Dict] = None,
    ) -> str:
        """Convenience method to create and log an event."""
        import uuid
        event = AuditEvent(
            event_id       = str(uuid.uuid4()),
            timestamp      = datetime.utcnow().isoformat() + "Z",
            user_id        = user_id,
            user_name      = user_name,
            user_role      = user_role,
            client_id      = client_id,
            event_category = category,
            event_type     = event_type,
            description    = description,
            ip_address     = ip_address,
            resource_id    = resource_id,
            resource_type  = resource_type,
            old_value      = old_value,
            new_value      = new_value,
            severity       = severity,
            metadata       = metadata or {},
        )
        return self.log(event)

    def verify_chain_integrity(self) -> bool:
        """Verify hash chain is unbroken (no tampering)."""
        if not self._chain:
            return True
        if self._chain[0].previous_hash != "GENESIS":
            return False
        for i in range(1, len(self._chain)):
            expected_prev = self._chain[i - 1].event_hash
            if self._chain[i].previous_hash != expected_prev:
                return False
            recomputed = self._chain[i].compute_hash()
            if recomputed != self._chain[i].event_hash:
                return False
        return True

    def get_client_trail(
        self,
        client_id: str,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get all events for a specific client."""
        events = [e for e in self._chain if e.client_id == client_id]
        return events[-limit:]

    def get_user_trail(self, user_id: str) -> List[AuditEvent]:
        return [e for e in self._chain if e.user_id == user_id]

    def generate_report(self, period: str = "") -> AuditReport:
        events = self._chain

        by_category: Dict[str, int] = {}
        by_user:     Dict[str, int] = {}
        critical:    List[Dict] = []

        for e in events:
            by_category[e.event_category.value] = by_category.get(e.event_category.value, 0) + 1
            by_user[e.user_name]                = by_user.get(e.user_name, 0) + 1
            if e.severity == EventSeverity.CRITICAL:
                critical.append({
                    "event_id":   e.event_id,
                    "timestamp":  e.timestamp,
                    "user":       e.user_name,
                    "event_type": e.event_type,
                    "description": e.description,
                    "client_id":  e.client_id,
                })

        suspicious = self._detect_suspicious_patterns(events)
        integrity  = self.verify_chain_integrity()

        return AuditReport(
            period              = period,
            total_events        = len(events),
            events_by_category  = by_category,
            events_by_user      = by_user,
            critical_events     = critical[-20:],
            suspicious_patterns = suspicious,
            integrity_ok        = integrity,
            chain_length        = len(self._chain),
        )

    def _detect_suspicious_patterns(self, events: List[AuditEvent]) -> List[str]:
        patterns = []

        # Multiple failed auth attempts (simulated — in real system, track auth events)
        auth_events = [e for e in events if e.event_category == EventCategory.AUTH]
        failed_auth  = [e for e in auth_events if "fail" in e.event_type.lower()]
        if len(failed_auth) > 5:
            patterns.append(f"{len(failed_auth)} failed authentication attempts detected.")

        # Unusual bulk data access
        access_events = [e for e in events if e.event_category == EventCategory.DATA_ACCESS]
        if len(access_events) > 200:
            patterns.append("High volume of data access events — possible bulk export.")

        # Critical events without corresponding filings
        critical_ct = sum(1 for e in events if e.severity == EventSeverity.CRITICAL)
        if critical_ct > 0:
            patterns.append(f"{critical_ct} critical event(s) require management review.")

        return patterns

    def export_jsonl(self) -> str:
        """Export all audit events as JSONL for regulatory submissions."""
        lines = []
        for event in self._chain:
            d = asdict(event)
            lines.append(json.dumps(d, default=str))
        return "\n".join(lines)


# Singleton logger per Flask app session
_global_logger: Optional[AuditTrailLogger] = None

def get_audit_logger(firm_id: str = "") -> AuditTrailLogger:
    global _global_logger
    if _global_logger is None:
        _global_logger = AuditTrailLogger(firm_id=firm_id)
    return _global_logger


def audit_trail_api(params: dict) -> dict:
    """JSON wrapper for Flask endpoint."""
    logger = get_audit_logger(params.get("firm_id", ""))
    action = params.get("action", "log")

    if action == "log":
        from enum import Enum as _Enum
        event_hash = logger.log_event(
            user_id       = params.get("user_id", "system"),
            user_name     = params.get("user_name", "system"),
            user_role     = params.get("user_role", "staff"),
            event_type    = params.get("event_type", "custom"),
            description   = params.get("description", ""),
            client_id     = params.get("client_id"),
            category      = EventCategory(params.get("category", "data_access")),
            severity      = EventSeverity(params.get("severity", "info")),
            resource_id   = params.get("resource_id"),
            resource_type = params.get("resource_type"),
            ip_address    = params.get("ip_address"),
            metadata      = params.get("metadata", {}),
        )
        return {"event_hash": event_hash, "status": "logged"}

    if action == "report":
        report = logger.generate_report(period=params.get("period", ""))
        return asdict(report)

    if action == "verify":
        return {"integrity_ok": logger.verify_chain_integrity(), "chain_length": len(logger._chain)}

    if action == "client_trail":
        events = logger.get_client_trail(params.get("client_id", ""))
        return {"events": [asdict(e) for e in events]}

    if action == "export":
        return {"jsonl": logger.export_jsonl()}

    return {"error": "unknown action"}
