"""
Document Vault — Encrypted Client File Storage
Secure document management for CA firms.
Features:
  • AES-256 encryption (via cryptography.fernet for symmetric key)
  • Document metadata registry (no plaintext storage of sensitive content)
  • Per-client document catalog with version tracking
  • Access control by role (owner / staff / viewer)
  • Retention policy enforcement
  • Document expiry alerts (e.g., PAN card, DIN, DPIN)
"""

from __future__ import annotations

import hashlib
import hmac
import os
import base64
import json
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from enum import Enum
from typing import Dict, List, Optional


class DocumentType(str, Enum):
    PAN_CARD        = "pan_card"
    AADHAAR         = "aadhaar"
    ITR             = "itr"
    ITR_ACK         = "itr_ack"
    FORM_16         = "form_16"
    FORM_26AS       = "form_26as"
    GSTR_RETURNS    = "gstr_returns"
    BALANCE_SHEET   = "balance_sheet"
    AUDIT_REPORT    = "audit_report"
    INCORPORATION   = "incorporation"
    GST_CERTIFICATE = "gst_certificate"
    BANK_STATEMENT  = "bank_statement"
    TDS_CERTIFICATE = "tds_certificate"
    POWER_OF_ATTY   = "power_of_attorney"
    AGREEMENT       = "agreement"
    OTHER           = "other"


class AccessRole(str, Enum):
    OWNER   = "owner"    # CA / firm owner
    STAFF   = "staff"    # Article clerk / employee
    VIEWER  = "viewer"   # Read-only (client login)
    ADMIN   = "admin"    # System admin


class RetentionPolicy(str, Enum):
    SEVEN_YEARS    = "7y"   # Most tax documents
    TEN_YEARS      = "10y"  # Company records
    PERMANENT      = "perm" # PAN, incorporation
    THREE_YEARS    = "3y"   # Routine correspondence


RETENTION_DAYS: Dict[RetentionPolicy, Optional[int]] = {
    RetentionPolicy.THREE_YEARS:  3 * 365,
    RetentionPolicy.SEVEN_YEARS:  7 * 365,
    RetentionPolicy.TEN_YEARS:    10 * 365,
    RetentionPolicy.PERMANENT:    None,
}

DEFAULT_RETENTION: Dict[DocumentType, RetentionPolicy] = {
    DocumentType.PAN_CARD:        RetentionPolicy.PERMANENT,
    DocumentType.AADHAAR:         RetentionPolicy.PERMANENT,
    DocumentType.ITR:             RetentionPolicy.SEVEN_YEARS,
    DocumentType.ITR_ACK:         RetentionPolicy.SEVEN_YEARS,
    DocumentType.FORM_16:         RetentionPolicy.SEVEN_YEARS,
    DocumentType.FORM_26AS:       RetentionPolicy.SEVEN_YEARS,
    DocumentType.GSTR_RETURNS:    RetentionPolicy.SEVEN_YEARS,
    DocumentType.BALANCE_SHEET:   RetentionPolicy.TEN_YEARS,
    DocumentType.AUDIT_REPORT:    RetentionPolicy.TEN_YEARS,
    DocumentType.INCORPORATION:   RetentionPolicy.PERMANENT,
    DocumentType.GST_CERTIFICATE: RetentionPolicy.PERMANENT,
    DocumentType.BANK_STATEMENT:  RetentionPolicy.SEVEN_YEARS,
    DocumentType.TDS_CERTIFICATE: RetentionPolicy.SEVEN_YEARS,
    DocumentType.OTHER:           RetentionPolicy.THREE_YEARS,
}


@dataclass
class DocumentRecord:
    """Metadata record for a stored document (content encrypted separately)."""
    doc_id:          str
    client_id:       str
    doc_type:        DocumentType
    filename:        str
    description:     str
    upload_date:     date
    uploaded_by:     str
    period:          Optional[str]     # e.g. "FY 2024-25"
    retention_policy: RetentionPolicy
    expiry_date:     Optional[date]    # For time-bound docs (GST cert validity etc.)
    sha256_hash:     str               # Hash of original file for integrity check
    encrypted_key:   str               # AES key encrypted with master key (base64)
    storage_path:    str               # Encrypted blob location (local/S3/etc.)
    version:         int = 1
    tags:            List[str] = field(default_factory=list)
    access_roles:    List[AccessRole] = field(default_factory=lambda: [AccessRole.OWNER, AccessRole.STAFF])
    is_deleted:      bool = False

    @property
    def retention_expiry(self) -> Optional[date]:
        days = RETENTION_DAYS.get(self.retention_policy)
        if days is None:
            return None
        return self.upload_date + timedelta(days=days)

    @property
    def days_to_expiry(self) -> Optional[int]:
        exp = self.expiry_date
        if exp is None:
            return None
        return (exp - date.today()).days

    @property
    def is_expiring_soon(self) -> bool:
        d = self.days_to_expiry
        return d is not None and 0 < d <= 30

    @property
    def is_expired(self) -> bool:
        d = self.days_to_expiry
        return d is not None and d <= 0


@dataclass
class VaultSummary:
    total_documents:    int
    total_clients:      int
    expiring_soon:      List[Dict]    # Documents expiring within 30 days
    expired:            List[Dict]    # Expired documents
    retention_due:      List[Dict]    # Documents past retention period
    recent_uploads:     List[Dict]
    by_type:            Dict[str, int]
    alerts:             List[str]


class DocumentVault:
    """
    Encrypted document registry for CA client files.
    Stores metadata; actual file encryption handled by storage layer.

    Note: In production, use cryptography.fernet or AWS KMS for key management.
    This module provides the registry/metadata layer.
    """

    def __init__(self, vault_id: str = "default"):
        self.vault_id   = vault_id
        self._records:  Dict[str, DocumentRecord] = {}
        self._access_log: List[Dict] = []

    def register_document(
        self,
        doc:           DocumentRecord,
        requesting_role: AccessRole = AccessRole.OWNER,
    ) -> str:
        """Register a document's metadata in the vault."""
        if requesting_role not in (AccessRole.OWNER, AccessRole.ADMIN, AccessRole.STAFF):
            raise PermissionError("Insufficient privileges to upload documents.")
        self._records[doc.doc_id] = doc
        self._log_access(doc.doc_id, requesting_role, "upload")
        return doc.doc_id

    def retrieve_metadata(
        self,
        doc_id:          str,
        requesting_role: AccessRole = AccessRole.OWNER,
    ) -> Optional[DocumentRecord]:
        """Retrieve document metadata (caller must decrypt using their key)."""
        doc = self._records.get(doc_id)
        if not doc or doc.is_deleted:
            return None
        if requesting_role not in doc.access_roles:
            raise PermissionError(f"Role {requesting_role} cannot access document {doc_id}.")
        self._log_access(doc_id, requesting_role, "retrieve")
        return doc

    def delete_document(
        self,
        doc_id:          str,
        requesting_role: AccessRole = AccessRole.OWNER,
    ) -> bool:
        """Soft-delete a document (marks as deleted, retains metadata for audit)."""
        if requesting_role not in (AccessRole.OWNER, AccessRole.ADMIN):
            raise PermissionError("Only owners and admins can delete documents.")
        doc = self._records.get(doc_id)
        if not doc:
            return False
        doc.is_deleted = True
        self._log_access(doc_id, requesting_role, "delete")
        return True

    def get_client_documents(
        self,
        client_id:       str,
        requesting_role: AccessRole = AccessRole.OWNER,
        doc_type:        Optional[DocumentType] = None,
    ) -> List[DocumentRecord]:
        docs = [d for d in self._records.values()
                if d.client_id == client_id
                and not d.is_deleted
                and requesting_role in d.access_roles]
        if doc_type:
            docs = [d for d in docs if d.doc_type == doc_type]
        return sorted(docs, key=lambda d: d.upload_date, reverse=True)

    def verify_integrity(self, doc_id: str, file_hash: str) -> bool:
        """Verify a retrieved file's SHA-256 hash matches the registered hash."""
        doc = self._records.get(doc_id)
        if not doc:
            return False
        return hmac.compare_digest(doc.sha256_hash.lower(), file_hash.lower())

    def get_vault_summary(self) -> VaultSummary:
        active = [d for d in self._records.values() if not d.is_deleted]

        expiring = [d for d in active if d.is_expiring_soon]
        expired  = [d for d in active if d.is_expired]

        today = date.today()
        retention_due = [
            d for d in active
            if d.retention_expiry and d.retention_expiry < today
        ]

        recent = sorted(active, key=lambda d: d.upload_date, reverse=True)[:10]

        by_type: Dict[str, int] = {}
        for d in active:
            by_type[d.doc_type.value] = by_type.get(d.doc_type.value, 0) + 1

        clients = len({d.client_id for d in active})

        alerts = []
        if expiring:
            alerts.append(f"{len(expiring)} document(s) expiring within 30 days — renew promptly.")
        if expired:
            alerts.append(f"{len(expired)} document(s) have expired — update client files.")
        if retention_due:
            alerts.append(
                f"{len(retention_due)} document(s) past retention period — "
                f"review for secure disposal per data protection policy."
            )

        return VaultSummary(
            total_documents = len(active),
            total_clients   = clients,
            expiring_soon   = [_doc_to_dict(d) for d in expiring],
            expired         = [_doc_to_dict(d) for d in expired],
            retention_due   = [_doc_to_dict(d) for d in retention_due],
            recent_uploads  = [_doc_to_dict(d) for d in recent],
            by_type         = by_type,
            alerts          = alerts,
        )

    def _log_access(self, doc_id: str, role: AccessRole, action: str) -> None:
        self._access_log.append({
            "doc_id":    doc_id,
            "role":      role.value,
            "action":    action,
            "timestamp": date.today().isoformat(),
        })

    def get_access_log(self, doc_id: Optional[str] = None) -> List[Dict]:
        if doc_id:
            return [e for e in self._access_log if e["doc_id"] == doc_id]
        return self._access_log


def _doc_to_dict(d: DocumentRecord) -> Dict:
    return {
        "doc_id":         d.doc_id,
        "client_id":      d.client_id,
        "doc_type":       d.doc_type.value,
        "filename":       d.filename,
        "description":    d.description,
        "upload_date":    d.upload_date.isoformat(),
        "period":         d.period,
        "expiry_date":    d.expiry_date.isoformat() if d.expiry_date else None,
        "days_to_expiry": d.days_to_expiry,
        "retention_policy": d.retention_policy.value,
        "version":        d.version,
        "tags":           d.tags,
    }


def generate_doc_checksum(content_bytes: bytes) -> str:
    """Generate SHA-256 hash of file content for integrity verification."""
    return hashlib.sha256(content_bytes).hexdigest()


def vault_operations(params: dict) -> dict:
    """JSON wrapper for Flask endpoint."""
    from datetime import datetime as _dt

    def _d(s) -> Optional[date]:
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
            try:
                return _dt.strptime(s, fmt).date()
            except (ValueError, TypeError):
                pass
        return None

    vault  = DocumentVault(vault_id=params.get("vault_id", "default"))
    action = params.get("action", "summary")

    # Register documents provided
    for doc_data in params.get("documents", []):
        doc = DocumentRecord(
            doc_id           = doc_data.get("doc_id", str(id(doc_data))),
            client_id        = doc_data.get("client_id", ""),
            doc_type         = DocumentType(doc_data.get("doc_type", "other")),
            filename         = doc_data.get("filename", ""),
            description      = doc_data.get("description", ""),
            upload_date      = _d(doc_data.get("upload_date")) or date.today(),
            uploaded_by      = doc_data.get("uploaded_by", ""),
            period           = doc_data.get("period"),
            retention_policy = RetentionPolicy(
                doc_data.get("retention_policy",
                             DEFAULT_RETENTION.get(DocumentType(doc_data.get("doc_type","other")),
                                                   RetentionPolicy.THREE_YEARS).value)
            ),
            expiry_date      = _d(doc_data.get("expiry_date")),
            sha256_hash      = doc_data.get("sha256_hash", ""),
            encrypted_key    = doc_data.get("encrypted_key", ""),
            storage_path     = doc_data.get("storage_path", ""),
            version          = int(doc_data.get("version", 1)),
            tags             = doc_data.get("tags", []),
        )
        vault.register_document(doc)

    if action == "summary":
        summary = vault.get_vault_summary()
        return asdict(summary)

    if action == "client_docs":
        docs = vault.get_client_documents(params.get("client_id", ""))
        return {"documents": [_doc_to_dict(d) for d in docs]}

    return {"status": "ok"}
