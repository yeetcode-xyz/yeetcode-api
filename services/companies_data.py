"""
Mock company-tagged problems data.

Final schema lives in `companies` and `company_problems` tables — this module
hands back the same shape so we can ship the UI before real data ingestion.
Replace with a DB-backed loader when the dataset arrives.
"""

from typing import Dict, List, Optional


COMPANIES: List[Dict] = [
    {"company_id": "google",   "slug": "google",   "name": "Google",    "logo_url": None},
    {"company_id": "meta",     "slug": "meta",     "name": "Meta",      "logo_url": None},
    {"company_id": "amazon",   "slug": "amazon",   "name": "Amazon",    "logo_url": None},
    {"company_id": "apple",    "slug": "apple",    "name": "Apple",     "logo_url": None},
    {"company_id": "microsoft","slug": "microsoft","name": "Microsoft", "logo_url": None},
    {"company_id": "netflix",  "slug": "netflix",  "name": "Netflix",   "logo_url": None},
    {"company_id": "uber",     "slug": "uber",     "name": "Uber",      "logo_url": None},
    {"company_id": "airbnb",   "slug": "airbnb",   "name": "Airbnb",    "logo_url": None},
    {"company_id": "stripe",   "slug": "stripe",   "name": "Stripe",    "logo_url": None},
    {"company_id": "linkedin", "slug": "linkedin", "name": "LinkedIn",  "logo_url": None},
    {"company_id": "tiktok",   "slug": "tiktok",   "name": "TikTok",    "logo_url": None},
    {"company_id": "salesforce","slug":"salesforce","name":"Salesforce","logo_url": None},
]


def _lc(slug: str, title: str, difficulty: str, frequency: int) -> Dict:
    return {
        "slug": slug,
        "title": title,
        "difficulty": difficulty,
        "leetcode_url": f"https://leetcode.com/problems/{slug}/",
        "frequency": frequency,
    }


PROBLEMS: Dict[str, List[Dict]] = {
    "google": [
        _lc("two-sum",                       "Two Sum",                       "easy",   95),
        _lc("longest-substring-without-repeating-characters", "Longest Substring Without Repeating Characters", "medium", 88),
        _lc("merge-intervals",               "Merge Intervals",               "medium", 84),
        _lc("word-ladder",                   "Word Ladder",                   "hard",   72),
        _lc("course-schedule",               "Course Schedule",               "medium", 70),
        _lc("number-of-islands",             "Number of Islands",             "medium", 66),
    ],
    "meta": [
        _lc("valid-palindrome",              "Valid Palindrome",              "easy",   91),
        _lc("kth-largest-element-in-an-array","Kth Largest Element in an Array","medium",83),
        _lc("subarray-sum-equals-k",         "Subarray Sum Equals K",         "medium", 80),
        _lc("binary-tree-vertical-order-traversal","Binary Tree Vertical Order Traversal","medium",75),
        _lc("minimum-remove-to-make-valid-parentheses","Minimum Remove to Make Valid Parentheses","medium",73),
    ],
    "amazon": [
        _lc("trapping-rain-water",           "Trapping Rain Water",           "hard",   86),
        _lc("lru-cache",                     "LRU Cache",                     "medium", 84),
        _lc("merge-k-sorted-lists",          "Merge k Sorted Lists",          "hard",   78),
        _lc("word-search",                   "Word Search",                   "medium", 70),
        _lc("rotting-oranges",               "Rotting Oranges",               "medium", 64),
    ],
    "apple": [
        _lc("group-anagrams",                "Group Anagrams",                "medium", 71),
        _lc("3sum",                          "3Sum",                          "medium", 69),
        _lc("longest-palindromic-substring", "Longest Palindromic Substring", "medium", 65),
        _lc("product-of-array-except-self",  "Product of Array Except Self",  "medium", 60),
    ],
    "microsoft": [
        _lc("reverse-linked-list",           "Reverse Linked List",           "easy",   88),
        _lc("validate-binary-search-tree",   "Validate Binary Search Tree",   "medium", 73),
        _lc("spiral-matrix",                 "Spiral Matrix",                 "medium", 65),
        _lc("rotate-image",                  "Rotate Image",                  "medium", 58),
    ],
    "netflix": [
        _lc("design-twitter",                "Design Twitter",                "medium", 70),
        _lc("encode-and-decode-tinyurl",     "Encode and Decode TinyURL",     "medium", 62),
        _lc("text-justification",            "Text Justification",            "hard",   55),
    ],
    "uber": [
        _lc("design-hit-counter",            "Design Hit Counter",            "medium", 75),
        _lc("logger-rate-limiter",           "Logger Rate Limiter",           "easy",   68),
        _lc("evaluate-division",             "Evaluate Division",             "medium", 60),
    ],
    "airbnb": [
        _lc("alien-dictionary",              "Alien Dictionary",              "hard",   72),
        _lc("design-search-autocomplete-system","Design Search Autocomplete System","hard",65),
        _lc("pour-water",                    "Pour Water",                    "medium", 50),
    ],
    "stripe": [
        _lc("currency-conversion-graph",     "Currency Conversion (graph DFS)","medium",78),
        _lc("rate-limiter",                  "Rate Limiter",                  "medium", 70),
        _lc("text-justification",            "Text Justification",            "hard",   58),
    ],
    "linkedin": [
        _lc("max-points-on-a-line",          "Max Points on a Line",          "hard",   72),
        _lc("nested-list-weight-sum",        "Nested List Weight Sum",        "easy",   66),
        _lc("can-place-flowers",             "Can Place Flowers",             "easy",   58),
    ],
    "tiktok": [
        _lc("longest-consecutive-sequence",  "Longest Consecutive Sequence",  "medium", 70),
        _lc("min-stack",                     "Min Stack",                     "medium", 64),
        _lc("decode-string",                 "Decode String",                 "medium", 60),
    ],
    "salesforce": [
        _lc("merge-two-sorted-lists",        "Merge Two Sorted Lists",        "easy",   73),
        _lc("count-and-say",                 "Count and Say",                 "medium", 60),
        _lc("integer-to-english-words",      "Integer to English Words",      "hard",   54),
    ],
}


def list_companies() -> List[Dict]:
    """Return all companies with problem counts."""
    return [
        {**c, "problem_count": len(PROBLEMS.get(c["company_id"], []))}
        for c in COMPANIES
    ]


def get_company(slug: str) -> Optional[Dict]:
    for c in COMPANIES:
        if c["slug"] == slug:
            return {**c, "problem_count": len(PROBLEMS.get(c["company_id"], []))}
    return None


def get_problems(company_id: str) -> List[Dict]:
    """Return problems for a company sorted by frequency desc."""
    return sorted(
        PROBLEMS.get(company_id, []),
        key=lambda p: p.get("frequency", 0),
        reverse=True,
    )
