"""Multilingual signals of prompt injection: English, Hindi, Hinglish, Kannada, Kanglish.

Injection text in tool descriptions and tool results tends to combine a few
moves: override earlier instructions, take a new role, act secretly, and send
data somewhere. Each move is a signal group with its own weight; a text is
risky when several groups fire together, not when one word appears (a weather
tool may legitimately say "send").

Each pattern is a regex applied to normalised text (see normalise()).
"""

import re
import unicodedata


# Invisible characters attackers use to hide instructions from human reviewers
INVISIBLE_CHARS = re.compile(
    "[​-‏‪-‮⁠-⁤﻿\U000e0000-\U000e007f]"
)


def normalise(text):
    """Lower-case, fold look-alike characters and drop invisible ones."""
    text = unicodedata.normalize("NFKC", text)
    text = INVISIBLE_CHARS.sub("", text)
    return text.lower()


def _group(*patterns):
    return [re.compile(pattern) for pattern in patterns]


# Words that mean "earlier instructions / rules" in each language
_RULES = (
    r"(instructions?|rules?|guidelines?|prompts?|directions?|niyam\w*|nirdesh\w*|hidayat\w*"
    r"|निर्देश\w*|नियम\w*|हिदायत\w*|suchane\w*|soochane\w*|ಸೂಚನೆ\w*|ನಿಯಮ\w*)"
)

SIGNALS = {
    # "Ignore / forget previous instructions"
    "override": (0.6, _group(
        r"\b(ignore|disregard|forget|override|bypass|skip)\b.{0,40}?\b(all|any|previous|prior|earlier|above|system)\b.{0,30}?" + _RULES,
        r"\b(ignore|disregard|forget)\b.{0,15}" + _RULES,
        r"(pichl\w*|pehle\s+wal\w*|purane|saare|sab)\s+.{0,30}?" + _RULES + r".{0,30}?(bhool|ignore|nazar\s?andaaz|chhod)",
        r"" + _RULES + r".{0,20}?(bhool\s+ja|ignore\s+kar|nazar\s?andaaz\s+kar|mat\s+maan)",
        r"(पिछल\S*|पुरान\S*|सभी|सारे)\s+.{0,30}?(निर्देश|नियम)\S*.{0,30}?(भूल|अनदेखा|नज़रअंदाज़|नजरअंदाज|छोड़)",
        r"(निर्देश|नियम)\S*\s+.{0,20}?(भूल\s+जा|अनदेखा\s+कर|मत\s+मान)",
        r"(hinde|hindina|modalina|ella)\s+.{0,30}?" + _RULES + r".{0,30}?(ignore|bitt\w*|marethu|mare\w*|nirlakshi\w*)",
        r"(ಹಿಂದಿನ|ಮೊದಲಿನ|ಎಲ್ಲಾ)\s+.{0,30}?(ಸೂಚನೆ|ನಿಯಮ)\S*.{0,30}?(ನಿರ್ಲಕ್ಷಿಸ|ಮರೆತು|ಮರೆಯ|ಬಿಟ್ಟು)",
        r"(ಸೂಚನೆ|ನಿಯಮ)\S*\s+.{0,20}?(ನಿರ್ಲಕ್ಷಿಸ|ಮರೆತು|ಮರೆಯ)",
    )),

    # "You are now admin", fake system messages, hidden directive tags
    "hijack": (0.4, _group(
        r"\byou\s+are\s+now\b",
        r"\b(admin|developer|god|debug|jailbreak|dan)\s+mode\b",
        r"<\s*/?\s*(important|system|instructions?|secret|admin)\s*>",
        r"^\s*(system|assistant)\s*:",
        r"\[(system|admin)\s*(override|message|note)?\]",
        r"\b(new|updated|real)\s+(system\s+)?instructions?\s*:",
        r"\bab\s+se\s+(tum|aap)\b",
        r"अब\s+से\s+(तुम|आप)",
        r"(ee\s*ga|iga|inmele)\s+(ninu|neevu)\b",
        r"(ಈಗಿನಿಂದ|ಇನ್ಮುಂದೆ|ಇನ್ನು\s+ಮುಂದೆ)\s+(ನೀನು|ನೀವು)",
        r"(ಸಿಸ್ಟಮ್|सिस्टम)\s*(ಸೂಚನೆ|संदेश|निर्देश|ಆದೇಶ)",
    )),

    # "Don't tell the user", "secretly", "silently"
    "secrecy": (0.4, _group(
        r"\b(do\s+not|don'?t|never)\s+(tell|inform|mention|reveal|show|notify)\b.{0,20}\b(user|human|them)\b",
        r"\b(secretly|silently|quietly|covertly|without\s+(telling|informing|asking)\s+(the\s+)?user)\b",
        r"\buser\s+ko\s+(mat|na|nahi)\s+(bata|bol|dikha)",
        r"\b(chupke|chupchap|chup\s+chap)\b",
        r"(उपयोगकर्ता|यूज़र|यूजर)\s+को\s+(मत|न|नहीं)\s+(बता|बोल|दिखा)",
        r"(चुपके|चुपचाप)",
        r"\b(user\s*(ge|ige)|yaarig\w*)\s+.{0,10}(helbeda|helabedi|heLbeDa|torisbeda)",
        r"(ಬಳಕೆದಾರ\S*|ಯಾರಿಗೂ)\s+.{0,15}(ಹೇಳಬೇಡ|ತೋರಿಸಬೇಡ)",
        r"(ಗುಟ್ಟಾಗಿ|ರಹಸ್ಯವಾಗಿ|ಸದ್ದಿಲ್ಲದೆ)",
    )),

    # "Send the phone number / notes / password to ..."
    "exfiltration": (0.5, _group(
        r"\b(send|forward|post|upload|leak|share|email|transmit|exfiltrate|copy)\b.{0,60}?\b(phone|number|contact|password|passwords|otp|notes?|profile|email|address|aadhaar|pan|secret|token|api\s?key|credentials?|history|conversation)\b",
        r"\b(phone|number|password|otp|notes?|profile|aadhaar|token|api\s?key|credentials?)\b.{0,60}?\b(bhej|send\s+kar|forward\s+kar|share\s+kar|daal\s+do|kalis\w*|kalsu|kodu|kaLis\w*)",
        r"(फ़ोन|फोन|नंबर|पासवर्ड|ओटीपी|नोट्स|प्रोफ़ाइल|आधार)\S*.{0,60}?(भेज|फ़ॉरवर्ड|शेयर)",
        r"(भेज|फ़ॉरवर्ड|शेयर)\S*.{0,60}?(फ़ोन|फोन|नंबर|पासवर्ड|नोट्स|प्रोफ़ाइल|आधार)",
        r"(ಫೋನ್|ನಂಬರ್|ಸಂಖ್ಯೆ|ಪಾಸ್\S*ವರ್ಡ್|ನೋಟ್ಸ್|ಪ್ರೊಫೈಲ್|ಆಧಾರ್)\S*.{0,60}?(ಕಳುಹಿಸ|ಕಳಿಸ|ಕೊಡು|ಹಂಚ)",
        r"\b(send|post|forward|bhej\w*|kalis\w*)\b.{0,40}?https?://",
    )),

    # Tool descriptions that steer other tools ("before using any tool, call X")
    "tool_steering": (0.3, _group(
        r"\b(before|after|whenever|every\s+time)\b.{0,40}?\b(using|calling|you\s+use|you\s+call)\b.{0,30}?\b(any|other|this|the)\b.{0,15}\btools?\b",
        r"\b(always|must|first)\b.{0,20}?\b(call|invoke|use|run)\b.{0,30}?\b(tool|function)\b",
        r"\b(instead\s+of|rather\s+than)\b.{0,30}?\b(tool|function)\b",
        r"\b(har\s+baar|hamesha|pehle)\b.{0,40}?\b(tool|function)\b.{0,20}?\b(call|use|chala)",
        r"\b(yaavaglu|modalu)\b.{0,40}?\b(tool)\b",
    )),
}

# Hidden content is suspicious on its own, whatever it says
OBFUSCATION = (0.5, _group(
    r"<!--.*?-->",
    r"\b[a-z0-9+/]{60,}={0,2}(?![a-z0-9+/])",
))

# Two or more different groups is the typical shape of a real attack
COMBO_BONUS = 0.2


def scan(text):
    """Return (score 0..1, findings) for one piece of text.

    findings: [{"signal": "override", "match": "...", "start": 3, "end": 40}]
    Offsets point into the original text where possible, so the UI can
    highlight the exact attack.
    """
    findings = []

    if INVISIBLE_CHARS.search(text):
        findings.append({"signal": "obfuscation", "match": "invisible characters", "start": None, "end": None})

    clean = normalise(text)

    # Offsets only line up when normalising didn't change the length
    same_layout = len(clean) == len(text)

    def record(signal, match):
        findings.append({
            "signal": signal,
            "match": match.group(0)[:160],
            "start": match.start() if same_layout else None,
            "end": match.end() if same_layout else None,
        })

    for signal, (_, patterns) in SIGNALS.items():
        for pattern in patterns:
            match = pattern.search(clean)

            if match:
                record(signal, match)
                break

    for pattern in OBFUSCATION[1]:
        match = pattern.search(clean)

        if match:
            record("obfuscation", match)
            break

    weights = dict((name, weight) for name, (weight, _) in SIGNALS.items())
    weights["obfuscation"] = OBFUSCATION[0]

    groups = {finding["signal"] for finding in findings}
    score = sum(weights[group] for group in groups)

    if len(groups) >= 2:
        score += COMBO_BONUS

    return min(round(score, 3), 1.0), findings
