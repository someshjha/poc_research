DERIVATION_SYSTEM = (
    "You are a physics research assistant. Be precise, show equations explicitly, "
    "and state assumptions. Keep the answer under 300 words."
)

REVIEW_SYSTEM = (
    "You are a skeptical peer reviewer for a physics paper. Find concrete gaps: "
    "unstated assumptions, validity ranges, unit consistency, and numerical caveats. "
    "Respond as a short bulleted list."
)

WRITEUP_SYSTEM = (
    "You are drafting a short results section for a physics paper. Be concise, "
    "cite the given sources by title, and state the numerical result clearly."
)


def derivation_prompt(question: str) -> str:
    return (
        f"Research question: {question}\n\n"
        "Propose a testable hypothesis, then derive the answer step by step, "
        "showing the key equations."
    )


def review_prompt(question: str, derivation: str, simulation: dict) -> str:
    return (
        f"Research question: {question}\n\n"
        f"Derivation under review:\n{derivation}\n\n"
        f"Numerical simulation result:\n{simulation}\n\n"
        "What should a careful reviewer double-check before this is published?"
    )


def writeup_prompt(question: str, derivation: str, simulation: dict, literature: list[dict], review: str) -> str:
    citations = "\n".join(f"- {p['title']} ({p['authors']})" for p in literature) or "(no citations retrieved)"
    return (
        f"Research question: {question}\n\n"
        f"Derivation:\n{derivation}\n\n"
        f"Simulation result:\n{simulation}\n\n"
        f"Reviewer notes:\n{review}\n\n"
        f"Available citations:\n{citations}\n\n"
        "Write a short results section (2-4 paragraphs) that states the question, "
        "the derived and numerically checked result, and references the citations "
        "above where relevant."
    )
