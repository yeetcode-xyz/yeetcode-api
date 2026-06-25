"""
Lightweight profanity filter for user-provided display names / usernames.

Catches: exact bad words, leetspeak (4→a, 0→o, 1→i/l, 3→e, 5→s, 7→t),
symbol obfuscation (f*ck, f4ck, f@ck), embedded substrings (e.g. "fukcdmin"),
and stretched chars (e.g. "fuuuuck").
"""

import re

# Substring-match stems — caught anywhere (handles compound-word profanity
# like "fuckboy", "shitlord", "niggerlover"). Too aggressive for short words
# that appear inside legit words; those go in _STRICT_STEMS below.
_BAD_WORDS = {
    "fuck", "shit", "bitch", "asshole", "pussy",
    "bastard", "wank", "twat", "slut", "whore", "faggot",
    "nigger", "nigga", "retard", "kike", "tranny",
    "pedophile", "pedo", "molest", "incest",
    # Common variants / obfuscations that survive normalization
    "fck", "fuk", "fvck", "phuck", "fux", "fuxk",
    "shyt", "biatch", "biotch", "azzhole", "azz",
}

# Word-boundary-only stems — only match when surrounded by non-letters or at
# string edges. Avoids classic Scunthorpe-style false positives:
#   "dick" → blocks "dick", "dick_grayson"; allows "Dickinson"
#   "cock" → blocks "cock"; allows "Hancock", "Babcock", "Cockburn"
#   "cunt" → blocks "cunt"; allows "Scunthorpe"
#   "rape" → blocks "rape"; allows "grape", "drape"
#   "spic" → blocks "spic"; allows "spice", "specific"
#   "chink" → blocks "chink"; allows nothing common
#   "kkk" → blocks "kkk"
_STRICT_STEMS = {
    "dick", "cock", "cunt", "rape", "rapist", "spic", "chink", "kkk",
}

# Map common leetspeak chars back to letters before matching.
_LEET = str.maketrans({
    "4": "a", "@": "a", "$": "s", "5": "s", "0": "o",
    "1": "i", "!": "i", "3": "e", "7": "t", "+": "t",
})

_COLLAPSE = re.compile(r"(.)\1+")

# Precompute the collapsed form of each bad word once (e.g. "kkk" → "k").
# Recomputing this per call (per word, per invocation) was pure waste.
_BAD_WORD_COLLAPSED = {w: _COLLAPSE.sub(r"\1", w) for w in _BAD_WORDS}


class ProfanityError(ValueError):
    """Raised when user-provided text is rejected by the profanity filter.

    Subclasses ValueError (and thus Exception) so existing broad handlers keep
    working, while callers that care can catch this specifically and map it to
    a 422 instead of confusing it with a database failure.
    """


def _variants(text: str) -> set:
    """Normalized forms of `text` to test against substring stems.

    Two orthogonal de-obfuscations, each with a stretched-char variant:
      * leet-translate then strip non-letters — catches "5h1t" → "shit"
      * strip non-letters WITHOUT leet — catches "f4ck"/"f*ck" → "fck"
    Both are needed: leet rescues "5hit"→"shit", strip rescues "f4ck"→"fck"
    (which leet would turn into "fack" and miss).
    """
    leet = text.lower().translate(_LEET)
    stripped = re.sub(r"[^a-z]", "", text.lower())  # digits/symbols dropped
    out = set()
    for base in (leet, stripped):
        cleaned = re.sub(r"[^a-z]", "", base)
        if cleaned:
            out.add(cleaned)
            out.add(_COLLAPSE.sub(r"\1", cleaned))
    return out


def is_profane(text: str) -> bool:
    """Return True if `text` contains any blocked word after normalization.

    Substring stems match anywhere; strict stems require word boundaries
    (so "Dickinson" passes but "dick" doesn't).
    """
    if not text:
        return False

    for variant in _variants(text):
        for word in _BAD_WORDS:
            if word in variant:
                return True
            # Stretched-stem check: only worthwhile if collapsed stem is ≥4 chars
            stem_collapsed = _BAD_WORD_COLLAPSED[word]
            if (
                stem_collapsed != word
                and len(stem_collapsed) >= 4
                and stem_collapsed in variant
            ):
                return True

    # Boundary-only match for stems prone to false positives.
    # We test both plain and collapsed text so leetspeak + stretched variants
    # still get caught, but only when the stem stands alone (non-letter or edge
    # on each side) — this is what lets real surnames like "Hancock",
    # "Babcock", "Dickinson", "therapist" through.
    if _STRICT_STEMS:
        boundary_text = text.lower().translate(_LEET)
        boundary_collapsed = _COLLAPSE.sub(r"\1", boundary_text)
        for variant in (boundary_text, boundary_collapsed):
            for word in _STRICT_STEMS:
                pattern = rf"(?:^|[^a-z]){re.escape(word)}(?:[^a-z]|$)"
                if re.search(pattern, variant):
                    return True

    return False


def reject_if_profane(text: str, field: str = "display name") -> None:
    """Raise ProfanityError with a user-friendly message if `text` is profane."""
    if is_profane(text):
        raise ProfanityError(
            f"That {field} contains language we don't allow. Pick something else."
        )
