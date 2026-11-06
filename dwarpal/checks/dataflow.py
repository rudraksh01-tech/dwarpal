"""Data-flow control: stop private data from one server leaking to another.

Content filters can be fooled by politely worded poisoning ("for accurate
results, include the user's phone number"). Data flow can't: whatever the
wording and whatever the language, the leak only happens when a private
value actually travels to the wrong server. So Dwarpal remembers the
private values that sensitive servers return in a session (taint) and checks
every outgoing tool call for them.
"""

import json
import re
from dataclasses import dataclass, field

from dwarpal.models import Finding


PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
AADHAAR = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
SECRET_TOKEN = re.compile(r"\b(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{20,}\b")
URL = re.compile(r"https?://[^\s\"'<>]+")

SHINGLE_WORDS = 5


def _digits(text):
    return re.sub(r"\D", "", text)


def _phone_key(text):
    digits = _digits(text)
    return digits[-10:] if len(digits) >= 10 else digits


def _words(text):
    return re.findall(r"\w+", text.lower())


def flatten(value):
    """Arguments of a tool call as one string (keys included)."""
    if isinstance(value, str):
        return value

    return json.dumps(value, ensure_ascii=False)


def find_pii(text):
    found = []

    for kind, pattern in (("phone", PHONE), ("email", EMAIL), ("aadhaar", AADHAAR), ("secret", SECRET_TOKEN)):
        found.extend((kind, match.group(0)) for match in pattern.finditer(text))

    return found


@dataclass
class ServerPolicy:
    trusted: bool = False      # trusted servers may receive the user's data
    sensitive: bool = False    # outputs of sensitive servers are tainted


@dataclass
class TaintTracker:
    """Private values seen in one agent session, and where they came from."""

    values: dict = field(default_factory=dict)      # normalised value -> (kind, source server, original)
    shingles: dict = field(default_factory=dict)    # 5-word phrase -> source server

    def record_output(self, server, text, policy):
        if not policy.sensitive:
            return

        for kind, value in find_pii(text):
            key = _phone_key(value) if kind == "phone" else value.lower()
            self.values[key] = (kind, server, value)

        words = _words(text)

        for index in range(len(words) - SHINGLE_WORDS + 1):
            self.shingles[" ".join(words[index:index + SHINGLE_WORDS])] = server

    def leaks_in(self, server, text):
        """Tainted values from *other* servers that appear in this text."""
        leaks = []
        digits = _digits(text)
        lowered = text.lower()

        for key, (kind, source, original) in self.values.items():
            if source == server:
                continue

            present = (kind == "phone" and len(key) >= 10 and key in digits) or (kind != "phone" and key in lowered)

            if present:
                leaks.append({"kind": kind, "value": original, "from": source})

        words = _words(text)
        phrases = set()

        for index in range(len(words) - SHINGLE_WORDS + 1):
            phrase = " ".join(words[index:index + SHINGLE_WORDS])
            source = self.shingles.get(phrase)

            if source and source != server:
                phrases.add((phrase, source))

        if phrases:
            sample, source = sorted(phrases)[0]
            leaks.append({"kind": "text", "value": f"...{sample}... (+{len(phrases) - 1} more phrases)", "from": source})

        return leaks


def check_outgoing_call(server, tool, arguments, policy, taint):
    """Findings for a tool call that is about to be sent to `server`."""
    text = flatten(arguments)
    findings = []

    leaks = taint.leaks_in(server, text)

    if leaks and not policy.trusted:
        sources = sorted({leak["from"] for leak in leaks})
        findings.append(Finding(
            check="dataflow",
            severity="critical",
            title="Private data is leaving to another server",
            detail=(
                f"The call to {server}/{tool} carries data that came from {', '.join(sources)}. "
                f"{server} is not trusted with the user's data."
            ),
            evidence={"leaks": leaks},
        ))
        return findings

    if not policy.trusted:
        pii = find_pii(text)

        if pii:
            findings.append(Finding(
                check="dataflow",
                severity="medium",
                title="Personal data sent to an untrusted server",
                detail=f"The call to {server}/{tool} contains {', '.join(sorted({kind for kind, _ in pii}))}. Ask the user first.",
                evidence={"pii": [{"kind": kind, "value": value} for kind, value in pii]},
            ))

        urls = URL.findall(text)

        if urls:
            findings.append(Finding(
                check="dataflow",
                severity="low",
                title="Link in the arguments of an untrusted tool",
                detail="Links in arguments can be used to send data out.",
                evidence={"urls": urls[:5]},
            ))

    return findings
