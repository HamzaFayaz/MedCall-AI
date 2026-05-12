import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "data" / "knowledge_base"
DEFAULT_KB_VERSION = "kb_v1"

APPROVED_KB_FILES = (
    "mercy_general_operational_policy.md",
    "department_services.md",
    "symptom_department_routing_guide.md",
    "faq_and_call_scripts.md",
)

SOURCE_TYPES = {
    "mercy_general_operational_policy.md": "operational_policy",
    "department_services.md": "department_services",
    "symptom_department_routing_guide.md": "symptom_routing",
    "faq_and_call_scripts.md": "faq_script",
}

DEPARTMENTS = (
    "Primary Care",
    "Emergency Medicine",
    "Pediatrics",
    "Women's Health",
    "Cardiology",
    "Orthopedics and Sports Medicine",
    "General Surgery",
    "Gastroenterology",
    "Neurology",
    "Psychiatry",
)

UNAVAILABLE_DEPARTMENTS = ("Dermatology", "Urology")


@dataclass(frozen=True)
class KnowledgeChunk:
    content: str
    source_file: str
    source_type: str
    section: str
    topic: str
    department: str | None
    allowed_claims: list[str]
    metadata: dict[str, Any]
    kb_version: str = DEFAULT_KB_VERSION

    def to_embedding_text(self) -> str:
        """Build the temporary text that will be embedded in Card 3."""
        lines = [
            f"Source type: {self.source_type}",
            f"Topic: {self.topic}",
            f"Section: {self.section}",
        ]

        if self.department:
            lines.append(f"Primary department: {self.department}")

        departments = self.metadata.get("departments_mentioned") or []
        if departments:
            lines.append(f"Departments mentioned: {'; '.join(departments)}")

        not_offered = self.metadata.get("not_offered_departments") or []
        if not_offered:
            lines.append(f"Departments not offered: {'; '.join(not_offered)}")

        if self.allowed_claims:
            lines.append(f"Allowed claims: {'; '.join(self.allowed_claims)}")

        lines.extend(["", "Content:", self.content])
        return "\n".join(lines)

    def to_supabase_payload(self) -> dict[str, Any]:
        """Return the row fields that exist before embedding is attached."""
        return asdict(self)


def normalize_markdown_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if line == "---":
            continue
        lines.append(line)

    normalized = "\n".join(lines).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def split_markdown_sections(markdown: str) -> list[tuple[str, str]]:
    """Split a markdown file into complete sections keyed by level-2 headings."""
    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", markdown, flags=re.MULTILINE))
    sections: list[tuple[str, str]] = []

    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        body = normalize_markdown_text(markdown[body_start:body_end])

        if body:
            sections.append((heading, body))

    return sections


def extract_question_examples(content: str) -> list[str]:
    if "Question examples:" not in content:
        return []

    after_label = content.split("Question examples:", 1)[1]
    before_answer = after_label.split("Approved answer:", 1)[0]
    examples = []

    for line in before_answer.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            examples.append(stripped[2:].strip())

    return examples


def extract_approved_answer(content: str) -> str | None:
    if "Approved answer:" not in content:
        return None

    answer_block = content.split("Approved answer:", 1)[1].strip()
    first_paragraph = answer_block.split("\n\n", 1)[0].strip()
    return first_paragraph.strip('"') or None


def find_departments(text: str) -> list[str]:
    lowered = text.lower()
    departments = []

    for department in DEPARTMENTS:
        names_to_check = [department.lower()]
        if department == "Women's Health":
            names_to_check.extend(["ob-gyn", "ob/gyn"])

        if any(name in lowered for name in names_to_check):
            departments.append(department)

    if "emergency department" in lowered and "Emergency Medicine" not in departments:
        departments.append("Emergency Medicine")

    return departments


def find_unavailable_departments(text: str) -> list[str]:
    return [
        department
        for department in UNAVAILABLE_DEPARTMENTS
        if re.search(rf"\b{re.escape(department)}\b", text, flags=re.IGNORECASE)
    ]


def infer_primary_department(source_type: str, section: str, content: str) -> str | None:
    if source_type == "department_services" and section in DEPARTMENTS:
        return section

    if source_type != "symptom_routing":
        return None

    departments = find_departments(content)
    if departments:
        return departments[0]

    return None


def build_allowed_claims(source_type: str, content: str, metadata: dict[str, Any]) -> list[str]:
    claims = {f"use_as_{source_type}"}
    lowered = content.lower()

    if "approved assistant wording:" in lowered or "approved answer:" in lowered:
        claims.add("use_approved_patient_facing_wording")

    if metadata["has_emergency_guidance"]:
        claims.add("use_emergency_escalation_for_red_flags")

    if metadata["requires_referral"]:
        claims.add("mention_referral_requirement")

    if metadata["has_not_offered_department"]:
        claims.add("do_not_claim_unavailable_department")
        claims.add("route_to_primary_care_or_front_desk")

    if "cannot authorize" in lowered:
        claims.add("do_not_authorize_refills_or_clinical_changes")

    if "must not promise" in lowered or "final coverage" in lowered:
        claims.add("do_not_guarantee_coverage_or_authorization")

    if "live availability" in lowered or "appointment slots" in lowered:
        claims.add("do_not_answer_live_availability_from_rag")

    return sorted(claims)


def has_emergency_guidance(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"\b911\b", text):
        return True

    emergency_patterns = (
        "emergency routing",
        "emergency symptoms",
        "emergency department routing applies",
        "route to emergency",
        "routed to emergency",
        "should be routed to emergency",
        "go to the nearest emergency",
    )
    return any(pattern in lowered for pattern in emergency_patterns)


def build_metadata(source_type: str, section: str, content: str) -> dict[str, Any]:
    lowered = content.lower()
    departments_mentioned = find_departments(f"{section}\n{content}")
    not_offered_departments = find_unavailable_departments(content)

    metadata: dict[str, Any] = {
        "departments_mentioned": departments_mentioned,
        "has_emergency_guidance": has_emergency_guidance(content),
        "requires_referral": "referral" in lowered or "requires pcp" in lowered,
        "has_not_offered_department": bool(not_offered_departments),
        "not_offered_departments": not_offered_departments,
    }

    if source_type == "faq_script":
        question_examples = extract_question_examples(content)
        approved_answer = extract_approved_answer(content)
        metadata["question_examples"] = question_examples
        metadata["has_approved_answer"] = approved_answer is not None
        if approved_answer:
            metadata["approved_answer"] = approved_answer

    if source_type == "operational_policy":
        metadata["has_approved_wording"] = "Approved assistant wording:" in content

    return metadata


def build_chunk(source_file: str, section: str, content: str, kb_version: str) -> KnowledgeChunk:
    source_type = SOURCE_TYPES[source_file]
    metadata = build_metadata(source_type, section, content)

    return KnowledgeChunk(
        content=content,
        source_file=source_file,
        source_type=source_type,
        section=section,
        topic=section,
        department=infer_primary_department(source_type, section, content),
        allowed_claims=build_allowed_claims(source_type, content, metadata),
        metadata=metadata,
        kb_version=kb_version,
    )


def load_knowledge_chunks(
    kb_dir: Path = KNOWLEDGE_BASE_DIR,
    kb_version: str = DEFAULT_KB_VERSION,
) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []

    for source_file in APPROVED_KB_FILES:
        file_path = kb_dir / source_file
        if not file_path.exists():
            raise FileNotFoundError(f"Approved RAG source file is missing: {file_path}")

        markdown = file_path.read_text(encoding="utf-8")
        for section, content in split_markdown_sections(markdown):
            chunks.append(build_chunk(source_file, section, content, kb_version))

    return chunks


def print_dry_run(chunks: list[KnowledgeChunk], sample_count: int) -> None:
    print(f"Loaded {len(chunks)} chunks from {len(APPROVED_KB_FILES)} approved KB files.")
    print()

    counts_by_source: dict[str, int] = {}
    for chunk in chunks:
        counts_by_source[chunk.source_file] = counts_by_source.get(chunk.source_file, 0) + 1

    print("Chunk counts by source file:")
    for source_file in APPROVED_KB_FILES:
        print(f"- {source_file}: {counts_by_source.get(source_file, 0)}")

    print()
    print(f"Sample chunks ({min(sample_count, len(chunks))}):")

    for chunk in chunks[:sample_count]:
        preview = {
            "source_file": chunk.source_file,
            "source_type": chunk.source_type,
            "section": chunk.section,
            "topic": chunk.topic,
            "department": chunk.department,
            "allowed_claims": chunk.allowed_claims,
            "metadata": chunk.metadata,
            "content_preview": chunk.content[:240],
            "embedding_text_preview": chunk.to_embedding_text()[:320],
        }
        print(json.dumps(preview, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load approved Mercy General KB chunks.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print chunk counts and sample chunks without writing to Supabase.",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=3,
        help="Number of sample chunks to show in dry-run output.",
    )
    parser.add_argument(
        "--kb-version",
        default=DEFAULT_KB_VERSION,
        help="Knowledge base version tag to attach to chunks.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = load_knowledge_chunks(kb_version=args.kb_version)

    if args.dry_run:
        print_dry_run(chunks, args.sample_count)
        return

    print("No write mode is implemented in Card 2. Use --dry-run to inspect chunks.")


if __name__ == "__main__":
    main()
