"""Tool integrity: pin each tool's descriptor and catch silent changes (rug pulls).

The first time Dwarpal sees a tool, it records a SHA-256 fingerprint of the
canonical descriptor (trust on first use, after the content checks pass).
Later listings are compared with the pin:

- same fingerprint: fine
- different fingerprint: the tool changed after it was approved. The change
  is measured as semantic drift (1 - cosine similarity of the old and new
  descriptions) and the new text is diffed, so a reviewer sees exactly what
  was added. The tool is held back until someone approves the new version.
"""

import difflib
from dataclasses import dataclass, field

from dwarpal import config, embeddings
from dwarpal.models import Finding


@dataclass
class Pin:
    server: str
    tool: str
    fingerprint: str
    canonical: str
    text: str                       # model-visible text, for drift and diffs
    approved: bool = True
    history: list = field(default_factory=list)   # earlier fingerprints


def text_diff(old, new):
    """Line diff as [{"op": "add"|"remove"|"same", "text": ...}] for the UI."""
    rows = []

    for line in difflib.ndiff(old.splitlines(), new.splitlines()):
        code, text = line[:2], line[2:]

        if code == "+ ":
            rows.append({"op": "add", "text": text})
        elif code == "- ":
            rows.append({"op": "remove", "text": text})
        elif code == "  ":
            rows.append({"op": "same", "text": text})

    return rows


def added_text(old, new):
    """Only the words that were added, which is where an attack would be."""
    old_words, new_words = old.split(), new.split()
    matcher = difflib.SequenceMatcher(a=old_words, b=new_words, autojunk=False)

    return " ".join(
        " ".join(new_words[j1:j2])
        for tag, _, _, j1, j2 in matcher.get_opcodes()
        if tag in ("insert", "replace")
    )


def check_integrity(descriptor, pin):
    """Compare a descriptor with its pin. Returns (status, findings, details)."""
    fingerprint = descriptor.fingerprint()
    text = descriptor.model_visible_text()

    if pin is None:
        return "new", [], {"fingerprint": fingerprint}

    if pin.fingerprint == fingerprint:
        return "unchanged", [], {"fingerprint": fingerprint}

    drift = round(1.0 - embeddings.cosine(pin.text, text), 3)
    meaning_changed = drift >= config.DRIFT_THRESHOLD

    details = {
        "fingerprint": fingerprint,
        "pinned_fingerprint": pin.fingerprint,
        "drift": drift,
        "drift_threshold": config.DRIFT_THRESHOLD,
        "diff": text_diff(pin.text, text),
        "added": added_text(pin.text, text),
        "embedding_backend": embeddings.backend_name(),
    }

    finding = Finding(
        check="descriptor",
        severity="critical" if meaning_changed else "high",
        title="Tool changed after approval (possible rug pull)",
        detail=(
            f"The description of {descriptor.key} no longer matches the approved version "
            f"(fingerprint changed, semantic drift {drift:.2f}). It is held back until re-approved."
        ),
        evidence=details,
    )

    return "changed", [finding], details
