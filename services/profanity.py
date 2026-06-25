"""
Lightweight profanity filter for user-provided display names / usernames.

Catches: exact bad words, leetspeak (4→a, 0→o, 1→i/l, 3→e, 5→s, 7→t),
embedded substrings (e.g. "fukcdmin"), and stretched chars (e.g. "fuuuuck").
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
    # Common variants
    "fck", "fuk", "shyt", "biatch", "azzhole",
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


def _normalize(text: str, *, collapse_singles: bool = False) -> str:
    """Lowercase, leet→ascii, optionally collapse repeats, strip non-letters."""
    s = text.lower().translate(_LEET)
    if collapse_singles:
        # Collapse 2+ repeats to 1 (fuuuuck → fuck) — for stretched-letter detection
        s = re.sub(r"(.)\1+", r"\1", s)
    # Strip whitespace, punctuation, and digits
    s = re.sub(r"[^a-z]", "", s)
    return s


def is_profane(text: str) -> bool:
    """Return True if `text` contains any blocked word after normalization.

    Two passes per stem set:
      1. Plain leet-normalize (preserves intentional doubles like "ass")
      2. Collapse-singles variant (catches stretched chars like "fuuuck")

    Substring stems match anywhere; strict stems require word boundaries
    (the original text, not normalized — so "Dickinson" passes but "dick" doesn't).
    """
    if not text:
        return False

    plain = _normalize(text)
    collapsed = _normalize(text, collapse_singles=True)

    # Substring match for stems that don't appear inside common English words
    for variant in (plain, collapsed):
        if not variant:
            continue
        for word in _BAD_WORDS:
            if word in variant:
                return True
            # Stretched-stem check: only worthwhile if collapsed stem is ≥4 chars
            stem_collapsed = re.sub(r"(.)\1+", r"\1", word)
            if (
                stem_collapsed != word
                and len(stem_collapsed) >= 4
                and stem_collapsed in variant
            ):
                return True

    # Boundary-only match for stems prone to false positives.
    # Build a regex that matches each strict stem only when surrounded by
    # non-letter chars (or string edges). We test both plain and collapsed
    # text so leetspeak + stretched variants still get caught.
    if _STRICT_STEMS:
        # Apply the strict check on the original-ish text — preserve digits/
        # punctuation as boundaries, but normalize case + leetspeak so attackers
        # can't bypass with "D!ck".
        boundary_text = text.lower().translate(_LEET)
        boundary_collapsed = re.sub(r"(.)\1+", r"\1", boundary_text)
        for variant in (boundary_text, boundary_collapsed):
            for word in _STRICT_STEMS:
                # Match: stem with non-letter (or start/end) on each side.
                # Trade-off: catches "FuckMyDick_" but not "SuckMyDick" (no
                # boundary before "dick"). Necessary to allow real surnames
                # like "Hancock", "Babcock", "Dickinson", "therapist".
                pattern = rf"(?:^|[^a-z]){re.escape(word)}(?:[^a-z]|$)"
                if re.search(pattern, variant):
                    return True

    return False


def reject_if_profane(text: str, field: str = "display name") -> None:
    """Raise an Exception with a user-friendly message if `text` is profane."""
    if is_profane(text):
        raise Exception(
            f"That {field} contains language we don't allow. Pick something else."
        )
