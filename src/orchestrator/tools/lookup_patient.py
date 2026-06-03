import re
from datetime import datetime
from typing import Any, Protocol

from src.config import config


class PatientLookupClient(Protocol):
    def query_patients(
        self,
        first_name: str,
        last_name: str,
        dob: str,
        phone_variants: list[str],
    ) -> list[dict[str, Any]]: ...


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


def phone_lookup_variants(phone: str) -> list[str]:
    """DB may store dashed numbers; try common formats."""
    raw = (phone or "").strip()
    digits = normalize_phone(raw)
    variants: list[str] = []
    for value in (raw, digits):
        if value and value not in variants:
            variants.append(value)
    if len(digits) == 10:
        dashed = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        if dashed not in variants:
            variants.append(dashed)
    return variants


def normalize_dob(dob: str) -> str:
    """Normalize to YYYY-MM-DD for Supabase DATE comparison."""
    raw = (dob or "").strip()
    if not raw:
        return raw
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def split_full_name(full_name: str) -> tuple[str, str]:
    """v1: last whitespace-separated token is last name."""
    parts = (full_name or "").strip().split()
    if len(parts) < 2:
        return (parts[0] if parts else "", "")
    return (" ".join(parts[:-1]), parts[-1])


def lookup_patient(
    first_name: str = "",
    last_name: str = "",
    dob: str = "",
    phone: str = "",
    *,
    full_name: str = "",
    client: PatientLookupClient | None = None,
) -> dict[str, Any]:
    """
    Supabase patients lookup on first_name + last_name + dob + phone.
    Returns {count, patient_id?} only — no field-level errors.
    """
    if full_name and (not first_name or not last_name):
        first_name, last_name = split_full_name(full_name)

    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    dob_norm = normalize_dob(dob)
    phone_variants = phone_lookup_variants(phone)

    if not all([first_name, last_name, dob_norm, phone_variants]):
        return {"count": 0}

    rows = _run_query(first_name, last_name, dob_norm, phone_variants, client)
    count = len(rows)
    result: dict[str, Any] = {"count": count}
    if count == 1:
        result["patient_id"] = rows[0].get("id")
    return result


def _run_query(
    first_name: str,
    last_name: str,
    dob: str,
    phone_variants: list[str],
    client: PatientLookupClient | None,
) -> list[dict[str, Any]]:
    if client is not None:
        return client.query_patients(first_name, last_name, dob, phone_variants)

    supabase_client = _create_supabase_client()
    response = (
        supabase_client.table("patients")
        .select("id")
        .eq("first_name", first_name)
        .eq("last_name", last_name)
        .eq("dob", dob)
        .in_("phone", phone_variants)
        .execute()
    )
    return list(response.data or [])


def _create_supabase_client() -> Any:
    url = config.SUPABASE_URL
    key = config.SUPABASE_SERVICE_ROLE_KEY or config.SUPABASE_KEY
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY) are required "
            "for lookup_patient."
        )
    from supabase import create_client

    return create_client(url, key)


class SupabasePatientLookupClient:
    """Injectable adapter wrapping Supabase table queries."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def query_patients(
        self,
        first_name: str,
        last_name: str,
        dob: str,
        phone_variants: list[str],
    ) -> list[dict[str, Any]]:
        response = (
            self._client.table("patients")
            .select("id")
            .eq("first_name", first_name)
            .eq("last_name", last_name)
            .eq("dob", dob)
            .in_("phone", phone_variants)
            .execute()
        )
        return list(response.data or [])
