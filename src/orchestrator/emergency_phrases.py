"""PRD emergency keyword categories and phrase lists (deterministic gate)."""

# reason_class -> phrases (matched after normalize_text in emergency_gate)
EMERGENCY_PHRASES: dict[str, tuple[str, ...]] = {
    "cardiac": (
        "chest pain",
        "crushing chest",
        "crushing chest pain",
        "heart attack",
        "having a heart attack",
        "pain in my chest",
        "pressure in my chest",
        "tightness in my chest",
    ),
    "breathing": (
        "difficulty breathing",
        "trouble breathing",
        "hard to breathe",
        "can't breathe",
        "cannot breathe",
        "can not breathe",
        "shortness of breath",
        "short of breath",
        "gasping for air",
        "not breathing",
        "stopped breathing",
        "choking",
    ),
    "stroke_neuro": (
        "sudden weakness",
        "drooping face",
        "face drooping",
        "facial drooping",
        "face is drooping",
        "slurred speech",
        "can't move my arm",
        "cannot move my arm",
        "one side weak",
        "sudden confusion",
        "sudden numbness",
        "stroke",
    ),
    "bleeding": (
        "severe bleeding",
        "bleeding heavily",
        "won't stop bleeding",
        "wont stop bleeding",
        "hemorrhaging",
        "hemorrhage",
        "bleeding out",
        "spurting blood",
    ),
    "suicidal": (
        "suicidal",
        "suicidal thoughts",
        "want to kill myself",
        "going to kill myself",
        "end my life",
        "hurt myself",
        "going to hurt myself",
        "kill myself",
    ),
    "allergic_severe": (
        "anaphylaxis",
        "anaphylactic",
        "throat closing",
        "throat is closing",
        "severe allergic reaction",
        "swelling throat",
        "can't swallow",
        "cannot swallow",
    ),
    "call_911": (
        "911",
        "nine one one",
        "call 911",
        "dial 911",
    ),
}

# Single-token or very short phrases that require word boundaries
WORD_BOUNDARY_PHRASES: frozenset[str] = frozenset(
    {
        "stroke",
        "911",
        "choking",
        "hemorrhage",
        "hemorrhaging",
        "anaphylaxis",
        "anaphylactic",
        "suicidal",
    }
)
