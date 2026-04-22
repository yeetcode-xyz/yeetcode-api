"""
SQLite database layer for YeetCode
Single source of truth — replaces DynamoDB + cache + WAL
"""

import sqlite3
import os

DB_PATH = os.environ.get("SQLITE_PATH", "/data/yeetcode.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    username            TEXT PRIMARY KEY,
    email               TEXT UNIQUE NOT NULL,
    display_name        TEXT,
    university          TEXT,
    is_guest            INTEGER DEFAULT 0,
    group_id            TEXT,
    easy                INTEGER DEFAULT 0,
    medium              INTEGER DEFAULT 0,
    hard                INTEGER DEFAULT 0,
    xp                  INTEGER DEFAULT 0,
    streak              INTEGER DEFAULT 0,
    last_completed_date TEXT,
    today               INTEGER DEFAULT 0,
    created_at          TEXT,
    updated_at          TEXT,
    leetcode_invalid    INTEGER DEFAULT 0,
    tag_stats           TEXT DEFAULT NULL,
    weekly_solved       INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_users_group ON users(group_id);
CREATE INDEX IF NOT EXISTS idx_users_university ON users(university);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS daily_problems (
    date        TEXT PRIMARY KEY,
    slug        TEXT NOT NULL,
    title       TEXT,
    frontend_id TEXT,
    difficulty  TEXT,
    tags        TEXT
);

CREATE TABLE IF NOT EXISTS daily_completions (
    username    TEXT NOT NULL,
    date        TEXT NOT NULL,
    PRIMARY KEY (username, date)
);
CREATE INDEX IF NOT EXISTS idx_completions_date ON daily_completions(date);
CREATE INDEX IF NOT EXISTS idx_completions_user ON daily_completions(username);

CREATE TABLE IF NOT EXISTS bounties (
    bounty_id        TEXT PRIMARY KEY,
    title            TEXT,
    description      TEXT,
    slug             TEXT,
    metric           TEXT,
    count            INTEGER,
    start_date       INTEGER,
    expiry_date      INTEGER,
    xp               INTEGER,
    tags             TEXT,
    difficulty_filter TEXT
);

CREATE TABLE IF NOT EXISTS bounty_progress (
    bounty_id    TEXT NOT NULL,
    username     TEXT NOT NULL,
    progress     INTEGER DEFAULT 0,
    baseline     INTEGER DEFAULT 0,
    xp_awarded   INTEGER DEFAULT 0,
    completed_at TEXT DEFAULT NULL,
    PRIMARY KEY (bounty_id, username)
);

CREATE TABLE IF NOT EXISTS duels (
    duel_id               TEXT PRIMARY KEY,
    challenger            TEXT NOT NULL,
    challengee            TEXT NOT NULL,
    problem_slug          TEXT,
    problem_title         TEXT,
    problem_number        TEXT,
    difficulty            TEXT,
    status                TEXT DEFAULT 'PENDING',
    is_wager              INTEGER DEFAULT 0,
    challenger_wager      INTEGER DEFAULT 0,
    challengee_wager      INTEGER DEFAULT 0,
    challenger_time       INTEGER DEFAULT -1,
    challengee_time       INTEGER DEFAULT -1,
    challenger_start_time TEXT,
    challengee_start_time TEXT,
    start_time            TEXT,
    winner                TEXT,
    xp_awarded            INTEGER DEFAULT 0,
    created_at            TEXT,
    accepted_at           TEXT,
    completed_at          TEXT,
    expires_at            INTEGER
);
CREATE INDEX IF NOT EXISTS idx_duels_challenger ON duels(challenger);
CREATE INDEX IF NOT EXISTS idx_duels_challengee ON duels(challengee);
CREATE INDEX IF NOT EXISTS idx_duels_status ON duels(status);

CREATE TABLE IF NOT EXISTS ai_duel_recaps (
    problem_slug      TEXT PRIMARY KEY,
    pattern_name      TEXT NOT NULL,
    takeaway          TEXT NOT NULL,
    similar_problems  TEXT NOT NULL,
    model_version     TEXT,
    created_at        TEXT,
    updated_at        TEXT
);

CREATE TABLE IF NOT EXISTS ai_problem_tags (
    problem_slug      TEXT PRIMARY KEY,
    tags              TEXT NOT NULL,
    fetched_at        TEXT
);

CREATE TABLE IF NOT EXISTS verification_codes (
    email       TEXT PRIMARY KEY,
    code        TEXT NOT NULL,
    expires_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS groups (
    group_id   TEXT PRIMARY KEY,
    name       TEXT,
    leader     TEXT NOT NULL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS duel_invites (
    token       TEXT PRIMARY KEY,
    challenger  TEXT NOT NULL,
    email       TEXT,
    difficulty  TEXT,
    created_at  TEXT,
    expires_at  INTEGER
);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    username    TEXT NOT NULL,
    endpoint    TEXT PRIMARY KEY,
    p256dh      TEXT NOT NULL,
    auth        TEXT NOT NULL,
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_push_username ON push_subscriptions(username);

CREATE TABLE IF NOT EXISTS blitz_questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL,
    difficulty  TEXT NOT NULL DEFAULT 'easy',
    question    TEXT NOT NULL,
    code        TEXT,
    options     TEXT NOT NULL,
    answer      TEXT NOT NULL,
    explanation TEXT
);

CREATE TABLE IF NOT EXISTS blitz_challenges (
    token          TEXT PRIMARY KEY,
    challenger     TEXT NOT NULL,
    question_ids   TEXT NOT NULL,
    time_limit_ms  INTEGER NOT NULL DEFAULT 60000,
    created_at     TEXT NOT NULL,
    expires_at     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS blitz_scores (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT NOT NULL,
    challenge_token TEXT,
    score        INTEGER NOT NULL,
    total        INTEGER NOT NULL,
    time_ms      INTEGER NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_blitz_scores_user ON blitz_scores(username);
"""


def get_db() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and row factory."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _migrate_blob_integers(conn):
    """
    One-time migration: rewrite BLOB-stored integers as proper SQLite integers.

    The DynamoDB → SQLite migration inserted Python Decimal values which
    sqlite3 serialized as BLOB bytes. Any arithmetic or comparison against
    those columns in SQL silently treats them as 0, breaking XP awards,
    bounty date filtering, etc.
    """
    # Table → integer columns that may contain BLOB-stored integers
    targets = {
        "users":           ["easy", "medium", "hard", "xp", "streak", "today", "leetcode_invalid"],
        "bounties":        ["count", "start_date", "expiry_date", "xp"],
        "bounty_progress": ["progress"],
        "duels":           ["is_wager", "challenger_wager", "challengee_wager",
                            "challenger_time", "challengee_time", "xp_awarded", "expires_at"],
    }

    for table, columns in targets.items():
        try:
            rows = conn.execute(f"SELECT rowid, * FROM {table}").fetchall()
        except Exception:
            continue  # table doesn't exist yet

        for row in rows:
            updates = {}
            for col in columns:
                val = row[col] if col in row.keys() else None
                if isinstance(val, (bytes, bytearray)):
                    updates[col] = int.from_bytes(val, "little")
            if updates:
                set_clause = ", ".join(f"{c} = ?" for c in updates)
                conn.execute(
                    f"UPDATE {table} SET {set_clause} WHERE rowid = ?",
                    list(updates.values()) + [row["rowid"]],
                )

    conn.commit()


def _migrate_add_columns(conn):
    """
    Safe ALTER TABLE migrations for new columns added after initial deployment.
    Each ALTER TABLE is wrapped in try/except — if the column already exists, it's a no-op.
    """
    additions = [
        ("users",           "tag_stats",          "TEXT DEFAULT NULL"),
        ("users",           "weekly_solved",       "INTEGER DEFAULT 0"),
        ("users",           "is_guest",            "INTEGER DEFAULT 0"),
        ("bounties",        "tags",                "TEXT"),
        ("bounties",        "difficulty_filter",   "TEXT"),
        ("bounty_progress", "baseline",            "INTEGER DEFAULT 0"),
        ("bounty_progress", "xp_awarded",          "INTEGER DEFAULT 0"),
        ("bounty_progress", "completed_at",        "TEXT DEFAULT NULL"),
        ("blitz_challenges", "time_limit_ms",       "INTEGER NOT NULL DEFAULT 60000"),
        ("duels",           "guest_challenger",     "INTEGER DEFAULT 0"),
        ("duel_invites",    "is_guest",             "INTEGER DEFAULT 0"),
        ("ai_duel_recaps",  "solve_strategy",       "TEXT"),
    ]
    for table, col, typedef in additions:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        except Exception:
            pass  # column already exists
    conn.commit()


DRAG_DROP_QUESTIONS = [
    {
        "category": "drag_drop", "difficulty": "easy",
        "question": "Complete the binary search function:",
        "code": "def binary_search(arr, target):\n    lo, hi = 0, len(arr) - 1\n    while lo [BLANK] hi:\n        mid = (lo + hi) [BLANK] 2\n        if arr[mid] == target: return mid\n        elif arr[mid] < target: lo = mid + 1\n        else: hi = mid - 1\n    return -1",
        "options": '["<=", "//", "<", "/", ">=", "**"]',
        "answer": '["<=", "//"]',
        "explanation": "Use <= to handle lo==hi case; // for integer floor division of midpoint."
    },
    {
        "category": "drag_drop", "difficulty": "easy",
        "question": "Complete the factorial function:",
        "code": "def factorial(n):\n    if n [BLANK] 1:\n        return 1\n    return n [BLANK] factorial(n - 1)",
        "options": '["<=", "*", "==", "+", ">=", "**"]',
        "answer": '["<=", "*"]',
        "explanation": "Base case n<=1 returns 1; recursive case multiplies n by factorial(n-1)."
    },
    {
        "category": "drag_drop", "difficulty": "easy",
        "question": "Complete the palindrome check:",
        "code": "def is_palindrome(s):\n    s = s.[BLANK]().replace(' ', '')\n    return s == s[BLANK]",
        "options": '["lower", "[::-1]", "upper", "[::1]", "strip", "reverse()"]',
        "answer": '["lower", "[::-1]"]',
        "explanation": "Lowercase first to normalize; s[::-1] reverses the string via slice notation."
    },
    {
        "category": "drag_drop", "difficulty": "easy",
        "question": "Complete the FizzBuzz core logic:",
        "code": "for i in range(1, 101):\n    if i [BLANK] 15 == 0:\n        print('FizzBuzz')\n    elif i % 3 [BLANK] 0:\n        print('Fizz')",
        "options": '["%", "==", "//", "!=", "<=", ">="]',
        "answer": '["%", "=="]',
        "explanation": "% is the modulo operator. Both checks use == to test for a zero remainder."
    },
    {
        "category": "drag_drop", "difficulty": "medium",
        "question": "Complete the bubble sort inner loop:",
        "code": "def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n - i [BLANK] 1):\n            if arr[j] [BLANK] arr[j + 1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]",
        "options": '["-", ">", "+", "<", "//", ">="]',
        "answer": '["-", ">"]',
        "explanation": "n-i-1 shrinks the inner range each pass; > swaps when left is greater."
    },
    {
        "category": "drag_drop", "difficulty": "medium",
        "question": "Complete the two-sum hashmap solution:",
        "code": "def two_sum(nums, target):\n    seen = {}\n    for i, num in [BLANK](nums):\n        comp = target [BLANK] num\n        if comp in seen:\n            return [seen[comp], i]\n        seen[num] = i",
        "options": '["enumerate", "-", "range", "+", "zip", "*"]',
        "answer": '["enumerate", "-"]',
        "explanation": "enumerate gives (index, value) pairs; complement = target - num."
    },
    {
        "category": "drag_drop", "difficulty": "medium",
        "question": "Complete the linked list prepend:",
        "code": "class Node:\n    def __init__(self, val):\n        self.val = val\n        self.[BLANK] = None\n\ndef prepend(head, val):\n    node = Node(val)\n    node.next = [BLANK]\n    return node",
        "options": '["next", "head", "val", "prev", "None", "self"]',
        "answer": '["next", "head"]',
        "explanation": "Nodes have a next pointer; new node's next points to the current head."
    },
    {
        "category": "drag_drop", "difficulty": "medium",
        "question": "Complete the BFS traversal:",
        "code": "from collections import deque\ndef bfs(graph, start):\n    visited, queue = set(), [BLANK]([start])\n    while queue:\n        node = queue.[BLANK]()\n        if node not in visited:\n            visited.add(node)\n            queue.extend(graph[node])\n    return visited",
        "options": '["deque", "popleft", "list", "pop", "append", "dict"]',
        "answer": '["deque", "popleft"]',
        "explanation": "deque enables O(1) popleft; popleft() ensures FIFO (queue) behavior."
    },
    {
        "category": "drag_drop", "difficulty": "hard",
        "question": "Complete the coin change DP solution:",
        "code": "def coin_change(coins, amount):\n    dp = [float('inf')] * (amount + 1)\n    dp[0] = [BLANK]\n    for coin in coins:\n        for x in range(coin, amount + 1):\n            dp[x] = [BLANK](dp[x], dp[x - coin] + 1)\n    return dp[amount] if dp[amount] != float('inf') else -1",
        "options": '["0", "min", "1", "max", "-1", "sum"]',
        "answer": '["0", "min"]',
        "explanation": "dp[0]=0 (base case: 0 coins needed for amount 0); min picks fewest coins."
    },
    {
        "category": "drag_drop", "difficulty": "hard",
        "question": "Complete the merge step of merge sort:",
        "code": "def merge(left, right):\n    result, i, j = [], 0, 0\n    while i < len(left) [BLANK] j < len(right):\n        if left[i] <= right[j]:\n            result.[BLANK](left[i]); i += 1\n        else:\n            result.append(right[j]); j += 1\n    return result + left[i:] + right[j:]",
        "options": '["and", "append", "or", "extend", "+", "pop"]',
        "answer": '["and", "append"]',
        "explanation": "Continue while BOTH arrays have elements (and); append smaller element."
    },
]

# ── MCQ questions (commented out for drag_drop testing) ──────────────────────
# To re-enable: change BLITZ_QUESTIONS below to BLITZ_QUESTIONS_MCQ + DRAG_DROP_QUESTIONS
BLITZ_QUESTIONS_MCQ = [
    # ── Output questions ──────────────────────────────────────────────────────
    {
        "category": "output", "difficulty": "easy",
        "question": "What does this print?",
        "code": "print(1 + 2 * 3)",
        "options": '["9","7","6","8"]',
        "answer": "7",
        "explanation": "Multiplication has higher precedence than addition. 2*3=6, then 1+6=7."
    },
    {
        "category": "output", "difficulty": "easy",
        "question": "What does this print?",
        "code": 'print("hello"[1:3])',
        "options": '["he","el","ell","elo"]',
        "answer": "el",
        "explanation": "Slicing [1:3] returns characters at index 1 and 2 (not 3)."
    },
    {
        "category": "output", "difficulty": "easy",
        "question": "What does this print?",
        "code": 'print(bool(""))',
        "options": '["True","False","None","Error"]',
        "answer": "False",
        "explanation": "Empty strings are falsy in Python."
    },
    {
        "category": "output", "difficulty": "easy",
        "question": "What does this print?",
        "code": "print(10 // 3)",
        "options": '["3.33","3","4","3.0"]',
        "answer": "3",
        "explanation": "// is floor (integer) division. 10 // 3 = 3."
    },
    {
        "category": "output", "difficulty": "easy",
        "question": "What does this print?",
        "code": "x = [1, 2, 3]\nprint(x[-1])",
        "options": '["1","2","3","Error"]',
        "answer": "3",
        "explanation": "Negative indexing: -1 is the last element."
    },
    {
        "category": "output", "difficulty": "easy",
        "question": "What does this print?",
        "code": 'print("ab" * 3)',
        "options": '["ababab","ab3","aabbcc","Error"]',
        "answer": "ababab",
        "explanation": "String multiplication repeats the string n times."
    },
    {
        "category": "output", "difficulty": "medium",
        "question": "What does this print?",
        "code": "a = [1, 2, 3]\nb = a\nb.append(4)\nprint(len(a))",
        "options": '["3","4","2","Error"]',
        "answer": "4",
        "explanation": "b = a copies the reference, not the list. Both point to the same object."
    },
    {
        "category": "output", "difficulty": "medium",
        "question": "What does this print?",
        "code": 'print(type(1/2).__name__)',
        "options": '["int","float","Fraction","number"]',
        "answer": "float",
        "explanation": "In Python 3, / always returns a float. Use // for integer division."
    },
    {
        "category": "output", "difficulty": "medium",
        "question": "What does this print?",
        "code": "print([i**2 for i in range(4)])",
        "options": '["[0,1,4,9]","[1,4,9,16]","[0,1,2,3]","[1,2,3,4]"]',
        "answer": "[0,1,4,9]",
        "explanation": "range(4) is 0,1,2,3. Squaring gives 0,1,4,9."
    },
    {
        "category": "output", "difficulty": "medium",
        "question": "What does this print?",
        "code": "d = {'a': 1, 'b': 2}\nprint(d.get('c', 0))",
        "options": '["None","0","Error","KeyError"]',
        "answer": "0",
        "explanation": "dict.get(key, default) returns the default if the key doesn't exist."
    },
    # ── Time complexity ───────────────────────────────────────────────────────
    {
        "category": "complexity", "difficulty": "easy",
        "question": "What is the time complexity of binary search?",
        "code": None,
        "options": '["O(n)","O(log n)","O(n log n)","O(1)"]',
        "answer": "O(log n)",
        "explanation": "Binary search halves the search space each step → O(log n)."
    },
    {
        "category": "complexity", "difficulty": "easy",
        "question": "What is the time complexity of accessing an element in an array by index?",
        "code": None,
        "options": '["O(n)","O(log n)","O(1)","O(n²)"]',
        "answer": "O(1)",
        "explanation": "Arrays are stored contiguously. Index access is a direct memory lookup."
    },
    {
        "category": "complexity", "difficulty": "easy",
        "question": "What is the worst-case time complexity of bubble sort?",
        "code": None,
        "options": '["O(n)","O(n log n)","O(n²)","O(log n)"]',
        "answer": "O(n²)",
        "explanation": "Bubble sort compares every pair — n*(n-1)/2 comparisons → O(n²)."
    },
    {
        "category": "complexity", "difficulty": "medium",
        "question": "What is the time complexity of merge sort?",
        "code": None,
        "options": '["O(n)","O(n²)","O(n log n)","O(log n)"]',
        "answer": "O(n log n)",
        "explanation": "Merge sort divides (log n levels) and merges (O(n) per level) → O(n log n)."
    },
    {
        "category": "complexity", "difficulty": "medium",
        "question": "What is the average time complexity of a hash table lookup?",
        "code": None,
        "options": '["O(n)","O(log n)","O(n log n)","O(1)"]',
        "answer": "O(1)",
        "explanation": "Hash tables use a hash function to jump directly to the bucket."
    },
    {
        "category": "complexity", "difficulty": "hard",
        "question": "What is the time complexity of naive recursive Fibonacci?",
        "code": "def fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)",
        "options": '["O(n)","O(n²)","O(2ⁿ)","O(n log n)"]',
        "answer": "O(2ⁿ)",
        "explanation": "Each call branches into 2 more calls, creating an exponential call tree."
    },
    # ── Concept MCQ ───────────────────────────────────────────────────────────
    {
        "category": "concept", "difficulty": "easy",
        "question": "Which data structure follows LIFO (Last In, First Out)?",
        "code": None,
        "options": '["Queue","Stack","Heap","Linked List"]',
        "answer": "Stack",
        "explanation": "A stack pops the most recently pushed item first — like a stack of plates."
    },
    {
        "category": "concept", "difficulty": "easy",
        "question": "Which traversal visits the root node first?",
        "code": None,
        "options": '["Inorder","Postorder","Preorder","Level-order"]',
        "answer": "Preorder",
        "explanation": "Preorder: Root → Left → Right."
    },
    {
        "category": "concept", "difficulty": "easy",
        "question": "What does a queue use?",
        "code": None,
        "options": '["LIFO","FIFO","FILO","LILO"]',
        "answer": "FIFO",
        "explanation": "Queue is First In, First Out — like a line at a checkout."
    },
    {
        "category": "concept", "difficulty": "medium",
        "question": "Which sorting algorithm is NOT stable?",
        "code": None,
        "options": '["Merge Sort","Bubble Sort","Insertion Sort","Quick Sort"]',
        "answer": "Quick Sort",
        "explanation": "Quick sort's partitioning can change the relative order of equal elements."
    },
    {
        "category": "concept", "difficulty": "medium",
        "question": "Which data structure is best for implementing a priority queue?",
        "code": None,
        "options": '["Stack","Queue","Heap","Array"]',
        "answer": "Heap",
        "explanation": "A min/max heap gives O(log n) insert and O(1) peek of the top priority item."
    },
    {
        "category": "concept", "difficulty": "medium",
        "question": "In a binary search tree, where is the smallest element?",
        "code": None,
        "options": '["Root","Rightmost node","Leftmost node","Any leaf"]',
        "answer": "Leftmost node",
        "explanation": "In a BST, all left children are smaller. The leftmost node is the minimum."
    },
    # ── Fill in the blank ─────────────────────────────────────────────────────
    {
        "category": "fill_blank", "difficulty": "easy",
        "question": "Complete: to check if a key exists in a Python dict:\n`if key ___ my_dict:`",
        "code": None,
        "options": '["in","==","has","contains"]',
        "answer": "in",
        "explanation": "The `in` operator checks for key membership in dicts, sets, and lists."
    },
    {
        "category": "fill_blank", "difficulty": "easy",
        "question": "Complete: to add an item to a Python list:\n`my_list.___(item)`",
        "code": None,
        "options": '["append","push","add","insert"]',
        "answer": "append",
        "explanation": "list.append(item) adds an item to the end of the list."
    },
    {
        "category": "fill_blank", "difficulty": "easy",
        "question": "Complete: to remove duplicates from a list:\n`unique = list(___(my_list))`",
        "code": None,
        "options": '["set","dict","sorted","unique"]',
        "answer": "set",
        "explanation": "Converting to a set removes duplicates, then back to list preserves the type."
    },
    {
        "category": "fill_blank", "difficulty": "medium",
        "question": "Complete: to get the length of a string s in Python:\n`n = ___(s)`",
        "code": None,
        "options": '["len","size","count","length"]',
        "answer": "len",
        "explanation": "len() is Python's built-in function for the length of any sequence."
    },
    {
        "category": "fill_blank", "difficulty": "medium",
        "question": "Complete: to sort a list in reverse order:\n`my_list.sort(reverse=___)`",
        "code": None,
        "options": '["True","False","1","desc"]',
        "answer": "True",
        "explanation": "reverse=True sorts in descending order."
    },
    # ── Bug fix ───────────────────────────────────────────────────────────────
    {
        "category": "bug", "difficulty": "easy",
        "question": "This function should return the sum of a list. What's the bug?",
        "code": "def total(nums):\n    sum = 0\n    for n in nums:\n        sum + n\n    return sum",
        "options": '["sum is a reserved word","sum + n should be sum += n","return should be outside the loop","range() is missing"]',
        "answer": "sum + n should be sum += n",
        "explanation": "`sum + n` computes but discards the result. `sum += n` actually updates sum."
    },
    {
        "category": "bug", "difficulty": "easy",
        "question": "This should print numbers 1 to 5. What's wrong?",
        "code": "for i in range(5):\n    print(i)",
        "options": '["range(5) gives 0-4, should be range(1,6)","print should be print(i+1) only","for loop syntax is wrong","Nothing, it is correct"]',
        "answer": "range(5) gives 0-4, should be range(1,6)",
        "explanation": "range(5) produces 0,1,2,3,4. Use range(1,6) to get 1,2,3,4,5."
    },
    {
        "category": "bug", "difficulty": "medium",
        "question": "This recursive function causes a stack overflow. Why?",
        "code": "def countdown(n):\n    print(n)\n    countdown(n - 1)",
        "options": '["n should be n+1","Missing base case to stop recursion","print should come after recursive call","countdown is misspelled"]',
        "answer": "Missing base case to stop recursion",
        "explanation": "Without `if n == 0: return`, the function recurses forever until a stack overflow."
    },
]

ADDITIONAL_DRAG_DROP = [
    {
        "category": "drag_drop", "difficulty": "easy",
        "question": "Complete the count function (drag the variable names):",
        "code": "def count(end):\n    for i in range([BLANK]):\n        print([BLANK])\n\ncount(5)",
        "options": '["end", "i", "0", "count", "start", "n"]',
        "answer": '["end", "i"]',
        "explanation": "range(end) iterates up to end; print(i) prints each loop variable."
    },
    {
        "category": "drag_drop", "difficulty": "medium",
        "question": "Complete the sliding window max sum (drag variable names):",
        "code": "def max_sum(arr, k):\n    window = sum(arr[:k])\n    best = [BLANK]\n    for i in range(k, len(arr)):\n        window += arr[i] - arr[i - k]\n        best = max([BLANK], window)\n    return best",
        "options": '["window", "best", "0", "k", "arr", "i"]',
        "answer": '["window", "best"]',
        "explanation": "best starts as the initial window sum; max(best, window) updates the running maximum."
    },
    {
        "category": "drag_drop", "difficulty": "medium",
        "question": "Complete the reverse linked list (drag pointer names):",
        "code": "def reverse(head):\n    prev = None\n    curr = [BLANK]\n    while curr:\n        nxt = curr.next\n        curr.next = [BLANK]\n        prev = curr\n        curr = nxt\n    return prev",
        "options": '["head", "prev", "nxt", "None", "curr", "node"]',
        "answer": '["head", "prev"]',
        "explanation": "curr starts at head; each node's next is redirected to prev to reverse the list."
    },
    {
        "category": "drag_drop", "difficulty": "medium",
        "question": "Complete the two-pointer valid palindrome check:",
        "code": "def is_palindrome(s):\n    left, right = 0, len(s) - 1\n    while [BLANK] < right:\n        if s[left] != s[[BLANK]]:\n            return False\n        left += 1\n        right -= 1\n    return True",
        "options": '["left", "right", "0", "len(s)", "mid", "i"]',
        "answer": '["left", "right"]',
        "explanation": "Loop while left < right; compare s[left] vs s[right] to check palindrome."
    },
    {
        "category": "drag_drop", "difficulty": "medium",
        "question": "Complete the DFS with an explicit stack:",
        "code": "def dfs(graph, start):\n    visited = set()\n    stack = [[BLANK]]\n    while stack:\n        node = stack.pop()\n        if node not in [BLANK]:\n            visited.add(node)\n            stack.extend(graph[node])\n    return visited",
        "options": '["start", "visited", "graph", "node", "stack", "set()"]',
        "answer": '["start", "visited"]',
        "explanation": "Stack begins with start node; skip if node already in visited set."
    },
    {
        "category": "drag_drop", "difficulty": "hard",
        "question": "Complete the memoized Fibonacci:",
        "code": "def fib(n, memo={}):\n    if n <= 1:\n        return n\n    if [BLANK] not in memo:\n        memo[[BLANK]] = fib(n-1, memo) + fib(n-2, memo)\n    return memo[n]",
        "options": '["n", "memo", "0", "1", "result", "cache"]',
        "answer": '["n", "n"]',
        "explanation": "Both checks use n as the key: `if n not in memo` and `memo[n] = ...`."
    },
    {
        "category": "drag_drop", "difficulty": "medium",
        "question": "Complete the valid parentheses checker:",
        "code": "def is_valid(s):\n    stack = []\n    pairs = {')': '(', '}': '{', ']': '['}\n    for [BLANK] in s:\n        if char in pairs:\n            if not stack or stack[-1] != pairs[[BLANK]]:\n                return False\n            stack.pop()\n        else:\n            stack.append(char)\n    return not stack",
        "options": '["char", "stack", "pairs", "s", "c", "key"]',
        "answer": '["char", "char"]',
        "explanation": "Iterate with variable `char`; look up the expected opener via `pairs[char]`."
    },
    {
        "category": "drag_drop", "difficulty": "hard",
        "question": "Complete the fast/slow pointer cycle detection:",
        "code": "def has_cycle(head):\n    slow = [BLANK]\n    fast = head\n    while fast and fast.next:\n        slow = slow.next\n        fast = fast.[BLANK].next\n        if slow == fast:\n            return True\n    return False",
        "options": '["head", "next", "slow", "fast", "None", "prev"]',
        "answer": '["head", "next"]',
        "explanation": "slow starts at head; fast advances two steps via fast.next.next."
    },
    {
        "category": "drag_drop", "difficulty": "medium",
        "question": "Complete the prefix sum array:",
        "code": "def prefix_sum(nums):\n    result = [0]\n    total = 0\n    for num in [BLANK]:\n        total += num\n        result.append([BLANK])\n    return result",
        "options": '["nums", "total", "num", "result", "0", "sum"]',
        "answer": '["nums", "total"]',
        "explanation": "Iterate over nums; append the running total to build the prefix sum array."
    },
    {
        "category": "drag_drop", "difficulty": "hard",
        "question": "Complete the backtracking subsets generator:",
        "code": "def subsets(nums):\n    result = []\n    def backtrack(start, [BLANK]):\n        result.append(list(path))\n        for i in range([BLANK], len(nums)):\n            path.append(nums[i])\n            backtrack(i + 1, path)\n            path.pop()\n    backtrack(0, [])\n    return result",
        "options": '["path", "start", "result", "i", "nums", "0"]',
        "answer": '["path", "start"]',
        "explanation": "path accumulates the current subset; start prevents re-using earlier elements."
    },
]

ADDITIONAL_QUESTIONS_MCQ = [
    # ── Dry run (trace the code) ──────────────────────────────────────────────
    {
        "category": "dry_run", "difficulty": "easy",
        "question": "What is the final value of x?",
        "code": "x = 0\nfor i in range(5):\n    x += i\nprint(x)",
        "options": '["10","15","4","5"]',
        "answer": "10",
        "explanation": "0+1+2+3+4 = 10."
    },
    {
        "category": "dry_run", "difficulty": "easy",
        "question": "What does this print?",
        "code": "stack = []\nstack.append(1)\nstack.append(2)\nstack.append(3)\nprint(stack.pop())",
        "options": '["1","2","3","[]"]',
        "answer": "3",
        "explanation": "pop() removes and returns the last element — stack (LIFO) returns 3."
    },
    {
        "category": "dry_run", "difficulty": "easy",
        "question": "What is the final value of result?",
        "code": "result = 1\nfor i in range(1, 5):\n    result *= i\nprint(result)",
        "options": '["24","120","10","4"]',
        "answer": "24",
        "explanation": "1*1*2*3*4 = 24 (4 factorial)."
    },
    {
        "category": "dry_run", "difficulty": "medium",
        "question": "What does this print?",
        "code": "def f(x):\n    return x * 2\n\nresult = list(map(f, [1, 2, 3]))\nprint(result)",
        "options": '["[2,4,6]","[1,2,3]","[1,4,9]","[2,3,4]"]',
        "answer": "[2,4,6]",
        "explanation": "map applies f to each element: 1*2=2, 2*2=4, 3*2=6."
    },
    {
        "category": "dry_run", "difficulty": "medium",
        "question": "What does this print?",
        "code": "from collections import deque\nq = deque([1, 2, 3])\nq.append(4)\nq.popleft()\nprint(list(q))",
        "options": '["[2,3,4]","[1,2,3]","[1,2,3,4]","[2,3]"]',
        "answer": "[2,3,4]",
        "explanation": "append(4) adds to right, popleft() removes 1 from left → [2,3,4]."
    },
    {
        "category": "dry_run", "difficulty": "medium",
        "question": "What is the final value of count?",
        "code": "nums = [1, 2, 3, 4, 5]\ncount = 0\nfor n in nums:\n    if n % 2 == 0:\n        count += 1\nprint(count)",
        "options": '["2","3","5","1"]',
        "answer": "2",
        "explanation": "Even numbers are 2 and 4 → count = 2."
    },
    {
        "category": "dry_run", "difficulty": "medium",
        "question": "What does this print?",
        "code": "d = {}\nfor c in 'abba':\n    d[c] = d.get(c, 0) + 1\nprint(d['a'])",
        "options": '["1","2","4","Error"]',
        "answer": "2",
        "explanation": "'a' appears twice in 'abba', so d['a'] = 2."
    },
    {
        "category": "dry_run", "difficulty": "hard",
        "question": "What does this print?",
        "code": "def mystery(n):\n    if n == 0:\n        return 0\n    return n + mystery(n - 1)\n\nprint(mystery(4))",
        "options": '["10","4","24","8"]',
        "answer": "10",
        "explanation": "4+3+2+1+0 = 10 (recursive sum)."
    },
    {
        "category": "dry_run", "difficulty": "hard",
        "question": "What does this print?",
        "code": "res = []\nfor i in range(3):\n    for j in range(3):\n        if i == j:\n            res.append(i)\nprint(res)",
        "options": '["[0,1,2]","[0,0,1,1,2,2]","[1,2,3]","[]"]',
        "answer": "[0,1,2]",
        "explanation": "i==j only on the diagonal: (0,0), (1,1), (2,2) → [0,1,2]."
    },
    {
        "category": "dry_run", "difficulty": "hard",
        "question": "What is the final value of dp[4]?",
        "code": "dp = [0] * 5\ndp[0] = 1\nfor i in range(1, 5):\n    dp[i] = dp[i-1] * 2\nprint(dp[4])",
        "options": '["8","16","4","32"]',
        "answer": "16",
        "explanation": "dp[0]=1, dp[1]=2, dp[2]=4, dp[3]=8, dp[4]=16."
    },
    # ── Technique (which algorithm/DS) ────────────────────────────────────────
    {
        "category": "technique", "difficulty": "easy",
        "question": "Find the shortest path in an unweighted graph. Which algorithm?",
        "code": None,
        "options": '["DFS","BFS","Dijkstra","Bellman-Ford"]',
        "answer": "BFS",
        "explanation": "BFS explores nodes level by level, guaranteeing the shortest path in unweighted graphs."
    },
    {
        "category": "technique", "difficulty": "easy",
        "question": "Check if a string has balanced parentheses. Which data structure?",
        "code": None,
        "options": '["Queue","Stack","Heap","Hash Map"]',
        "answer": "Stack",
        "explanation": "Push opening brackets; pop and match on closing brackets. LIFO = stack."
    },
    {
        "category": "technique", "difficulty": "easy",
        "question": "Detect if a linked list has a cycle. Which technique?",
        "code": None,
        "options": '["Hash Set","Fast/Slow Pointers","BFS","Binary Search"]',
        "answer": "Fast/Slow Pointers",
        "explanation": "Floyd's cycle detection: fast pointer meets slow pointer inside the cycle."
    },
    {
        "category": "technique", "difficulty": "medium",
        "question": "Find the kth largest element in an array. Which is most efficient?",
        "code": None,
        "options": '["Sort descending","Min-heap of size k","Max-heap","Counting sort"]',
        "answer": "Min-heap of size k",
        "explanation": "Maintain a min-heap of k elements. O(n log k) vs O(n log n) for full sort."
    },
    {
        "category": "technique", "difficulty": "medium",
        "question": "Find two numbers in a sorted array that sum to a target. Best approach?",
        "code": None,
        "options": '["Nested loops O(n²)","Two pointers O(n)","Binary search O(n log n)","Hash map O(n)"]',
        "answer": "Two pointers O(n)",
        "explanation": "Move left pointer right if sum is too small, right pointer left if too large."
    },
    {
        "category": "technique", "difficulty": "medium",
        "question": "Count frequency of each character in a string. Best data structure?",
        "code": None,
        "options": '["Array","Linked List","Hash Map","Stack"]',
        "answer": "Hash Map",
        "explanation": "Hash maps give O(1) average insert and lookup for character → count mapping."
    },
    {
        "category": "technique", "difficulty": "medium",
        "question": "Find the minimum cost to reach every node from a source (weighted graph). Which algorithm?",
        "code": None,
        "options": '["BFS","DFS","Dijkstra","Merge Sort"]',
        "answer": "Dijkstra",
        "explanation": "Dijkstra's uses a min-heap to greedily pick the shortest unvisited node."
    },
    {
        "category": "technique", "difficulty": "hard",
        "question": "Find the minimum number of coins to make change. Which paradigm?",
        "code": None,
        "options": '["Greedy","Dynamic Programming","BFS","Divide and Conquer"]',
        "answer": "Dynamic Programming",
        "explanation": "Greedy fails for arbitrary coin sets. DP builds optimal solutions bottom-up."
    },
    {
        "category": "technique", "difficulty": "hard",
        "question": "Find the largest rectangle in a histogram. Which data structure?",
        "code": None,
        "options": '["Queue","Two Pointers","Monotonic Stack","Segment Tree"]',
        "answer": "Monotonic Stack",
        "explanation": "A monotonic stack tracks bars in increasing height, enabling O(n) area calculation."
    },
    {
        "category": "technique", "difficulty": "hard",
        "question": "Generate all valid combinations (e.g., subsets, permutations). Which technique?",
        "code": None,
        "options": '["BFS","Greedy","Backtracking","Memoization"]',
        "answer": "Backtracking",
        "explanation": "Backtracking explores all paths and prunes invalid branches, ideal for combinatorics."
    },
    # ── Extra complexity ──────────────────────────────────────────────────────
    {
        "category": "complexity", "difficulty": "easy",
        "question": "What is the time complexity of this code?",
        "code": "for i in range(n):\n    for j in range(n):\n        print(i, j)",
        "options": '["O(n)","O(n²)","O(n log n)","O(2n)"]',
        "answer": "O(n²)",
        "explanation": "Two nested loops each running n times = n*n = O(n²)."
    },
    {
        "category": "complexity", "difficulty": "medium",
        "question": "What is the time complexity of this code?",
        "code": "i = n\nwhile i > 1:\n    i = i // 2",
        "options": '["O(n)","O(log n)","O(n log n)","O(1)"]',
        "answer": "O(log n)",
        "explanation": "i is halved each iteration, so the loop runs log₂(n) times."
    },
    {
        "category": "complexity", "difficulty": "medium",
        "question": "What is the space complexity of DFS on a graph with V nodes?",
        "code": None,
        "options": '["O(1)","O(V)","O(V²)","O(E)"]',
        "answer": "O(V)",
        "explanation": "The recursion stack and visited set each hold at most V nodes."
    },
    {
        "category": "complexity", "difficulty": "medium",
        "question": "What is the time complexity of inserting into a binary heap?",
        "code": None,
        "options": '["O(1)","O(log n)","O(n)","O(n log n)"]',
        "answer": "O(log n)",
        "explanation": "After insertion at the end, the element bubbles up at most log n levels."
    },
    {
        "category": "complexity", "difficulty": "hard",
        "question": "What is the time complexity?",
        "code": "for i in range(n):\n    j = 1\n    while j < n:\n        j *= 2",
        "options": '["O(n²)","O(n log n)","O(log n)","O(n)"]',
        "answer": "O(n log n)",
        "explanation": "Outer loop O(n), inner loop doubles j so it runs O(log n) times → O(n log n)."
    },
    {
        "category": "complexity", "difficulty": "hard",
        "question": "What is the space complexity of merge sort?",
        "code": None,
        "options": '["O(1)","O(log n)","O(n)","O(n log n)"]',
        "answer": "O(n)",
        "explanation": "Merge sort creates temporary arrays during merging totaling O(n) extra space."
    },
    # ── Extra concept ─────────────────────────────────────────────────────────
    {
        "category": "concept", "difficulty": "easy",
        "question": "What is memoization?",
        "code": None,
        "options": '["Sorting results","Caching function results to avoid recomputation","Compressing data","Hashing inputs"]',
        "answer": "Caching function results to avoid recomputation",
        "explanation": "Memoization stores outputs of expensive function calls, returning cached results on repeat inputs."
    },
    {
        "category": "concept", "difficulty": "easy",
        "question": "What makes a graph a DAG?",
        "code": None,
        "options": '["It is undirected","It has no cycles and edges are directed","It has weighted edges","All nodes have equal degree"]',
        "answer": "It has no cycles and edges are directed",
        "explanation": "DAG = Directed Acyclic Graph. Directed edges + no cycles."
    },
    {
        "category": "concept", "difficulty": "medium",
        "question": "What is the key difference between BFS and DFS?",
        "code": None,
        "options": '["BFS uses a stack, DFS uses a queue","BFS uses a queue and explores level by level; DFS uses a stack and goes deep first","BFS is only for trees","DFS cannot find shortest paths"]',
        "answer": "BFS uses a queue and explores level by level; DFS uses a stack and goes deep first",
        "explanation": "BFS (queue/FIFO) finds shortest paths in unweighted graphs; DFS (stack/LIFO) is better for path existence and cycle detection."
    },
    {
        "category": "concept", "difficulty": "medium",
        "question": "How does a hash table handle collisions via chaining?",
        "code": None,
        "options": '["Overwrites the existing key","Finds the next empty slot","Each bucket holds a linked list of entries","Resizes the table"]',
        "answer": "Each bucket holds a linked list of entries",
        "explanation": "Separate chaining stores multiple key-value pairs at the same bucket using a linked list."
    },
    {
        "category": "concept", "difficulty": "medium",
        "question": "What is amortized O(1) time for dynamic array append?",
        "code": None,
        "options": '["Every append is O(1)","Most appends are O(1); occasional resize is O(n) but cost is spread over n operations","Append is O(log n) average","Append is O(n) worst case always"]',
        "answer": "Most appends are O(1); occasional resize is O(n) but cost is spread over n operations",
        "explanation": "Doubling strategy means resizes happen rarely. Total cost for n appends is O(n) → O(1) amortized."
    },
    {
        "category": "concept", "difficulty": "hard",
        "question": "What is a topological sort used for?",
        "code": None,
        "options": '["Sorting numbers","Ordering nodes in a DAG so all edges go forward","Finding shortest paths","Detecting cycles in undirected graphs"]',
        "answer": "Ordering nodes in a DAG so all edges go forward",
        "explanation": "Topological sort produces a linear ordering of a DAG's nodes — used in task scheduling, build systems, etc."
    },
    # ── Extra bug ─────────────────────────────────────────────────────────────
    {
        "category": "bug", "difficulty": "easy",
        "question": "This should return the last element. What's wrong?",
        "code": "def last(arr):\n    return arr[len(arr)]",
        "options": '["Should use arr[-1] or arr[len(arr)-1]","arr should be a list","return is missing","len() is wrong"]',
        "answer": "Should use arr[-1] or arr[len(arr)-1]",
        "explanation": "arr[len(arr)] is one past the end — IndexError. Valid last index is len(arr)-1."
    },
    {
        "category": "bug", "difficulty": "medium",
        "question": "This should remove evens. What's the bug?",
        "code": "nums = [1, 2, 3, 4, 5]\nfor n in nums:\n    if n % 2 == 0:\n        nums.remove(n)\nprint(nums)",
        "options": '["remove() is wrong method","Modifying a list while iterating over it skips elements","Should use filter()","range() is missing"]',
        "answer": "Modifying a list while iterating over it skips elements",
        "explanation": "Removing items shifts indices mid-iteration. Build a new list or iterate a copy instead."
    },
    {
        "category": "bug", "difficulty": "medium",
        "question": "This function has a subtle bug. What is it?",
        "code": "def add_item(item, lst=[]):\n    lst.append(item)\n    return lst",
        "options": '["append is wrong","Default mutable argument is shared across all calls","item and lst are swapped","Missing return type"]',
        "answer": "Default mutable argument is shared across all calls",
        "explanation": "Default arguments are evaluated once. The same list is reused each call, causing unexpected accumulation."
    },
    {
        "category": "bug", "difficulty": "hard",
        "question": "Binary search returns wrong results. What's the bug?",
        "code": "def binary_search(arr, t):\n    lo, hi = 0, len(arr)\n    while lo < hi:\n        mid = (lo + hi) // 2\n        if arr[mid] == t: return mid\n        elif arr[mid] < t: lo = mid + 1\n        else: hi = mid - 1\n    return -1",
        "options": '["lo should start at -1","hi should be len(arr)-1 to avoid index out of range","mid calculation is wrong","The while condition should be lo <= hi"]',
        "answer": "hi should be len(arr)-1 to avoid index out of range",
        "explanation": "hi = len(arr) can cause arr[mid] to be out of bounds when lo=0 and hi=len(arr)."
    },
    {
        "category": "bug", "difficulty": "hard",
        "question": "This recursive function always returns None. Why?",
        "code": "def find(node, target):\n    if node is None:\n        return None\n    if node.val == target:\n        return node\n    find(node.left, target)\n    find(node.right, target)",
        "options": '["Missing base case","Recursive calls are not returned","node.val comparison is wrong","Should use BFS instead"]',
        "answer": "Recursive calls are not returned",
        "explanation": "Without `return find(...)`, the result of recursive calls is discarded. Add `return` before each recursive call."
    },
    # ── Extra output ──────────────────────────────────────────────────────────
    {
        "category": "output", "difficulty": "medium",
        "question": "What does this print?",
        "code": "def make_adder(n):\n    return lambda x: x + n\n\nadd5 = make_adder(5)\nprint(add5(3))",
        "options": '["5","3","8","Error"]',
        "answer": "8",
        "explanation": "make_adder(5) returns a closure capturing n=5. add5(3) returns 3+5=8."
    },
    {
        "category": "output", "difficulty": "medium",
        "question": "What does this print?",
        "code": "x = [1, 2, 3]\ny = x[:]\ny.append(4)\nprint(len(x), len(y))",
        "options": '["3 3","4 4","3 4","4 3"]',
        "answer": "3 4",
        "explanation": "x[:] creates a shallow copy. Appending to y does not affect x."
    },
    {
        "category": "output", "difficulty": "hard",
        "question": "What does this print?",
        "code": "fns = []\nfor i in range(3):\n    fns.append(lambda: i)\nprint([f() for f in fns])",
        "options": '["[0,1,2]","[2,2,2]","[0,0,0]","Error"]',
        "answer": "[2,2,2]",
        "explanation": "Python closures capture the variable i by reference, not by value. After the loop i=2, so all lambdas return 2."
    },
    {
        "category": "output", "difficulty": "medium",
        "question": "What does this print?",
        "code": "print(0.1 + 0.2 == 0.3)",
        "options": '["True","False","Error","None"]',
        "answer": "False",
        "explanation": "Floating-point arithmetic is inexact. 0.1+0.2 = 0.30000000000000004 in IEEE 754."
    },
    {
        "category": "output", "difficulty": "hard",
        "question": "What does this print?",
        "code": "class A:\n    x = 0\n\na = A()\nb = A()\na.x = 5\nprint(A.x, b.x)",
        "options": '["5 5","0 0","0 5","5 0"]',
        "answer": "0 0",
        "explanation": "a.x = 5 creates an instance attribute on a only; the class attribute A.x and b.x remain 0."
    },
]

ADDITIONAL_QUESTIONS = ADDITIONAL_DRAG_DROP + ADDITIONAL_QUESTIONS_MCQ

BLITZ_QUESTIONS = BLITZ_QUESTIONS_MCQ + DRAG_DROP_QUESTIONS + ADDITIONAL_QUESTIONS


def _seed_blitz_questions(conn):
    """Seed blitz questions. Re-seeds when the question list has grown."""
    count = conn.execute("SELECT COUNT(*) FROM blitz_questions").fetchone()[0]
    if count >= len(BLITZ_QUESTIONS):
        return
    conn.execute("DELETE FROM blitz_questions")
    for q in BLITZ_QUESTIONS:
        conn.execute(
            """INSERT INTO blitz_questions (category, difficulty, question, code, options, answer, explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [q["category"], q["difficulty"], q["question"], q.get("code"),
             q["options"], q["answer"], q.get("explanation")],
        )
    conn.commit()


def _seed_roadmap_table(conn, table_name: str, problems: list):
    """Seed a roadmap problem table. Re-inserts if count doesn't match (handles updates)."""
    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    if count == len(problems):
        return
    conn.execute(f"DELETE FROM {table_name}")
    for p in problems:
        conn.execute(
            f"""INSERT INTO {table_name} (category, title, slug, difficulty, problem_number)
               VALUES (?, ?, ?, ?, ?)""",
            [p["category"], p["title"], p["slug"], p["difficulty"], p.get("problem_number")],
        )
    conn.commit()


def _seed_roadmap_problems(conn):
    """Seed Blind 75, NeetCode 150, and NeetCode 250 problem lists."""
    from roadmap_data import BLIND75_PROBLEMS, NEETCODE150_PROBLEMS, NEETCODE250_PROBLEMS
    _seed_roadmap_table(conn, "blind75_problems", BLIND75_PROBLEMS)
    _seed_roadmap_table(conn, "neetcode150_problems", NEETCODE150_PROBLEMS)
    _seed_roadmap_table(conn, "neetcode250_problems", NEETCODE250_PROBLEMS)


def init_db():
    """Initialize database schema and run one-time data migrations on startup."""
    # Ensure parent directory exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = get_db()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    _migrate_blob_integers(conn)
    _migrate_add_columns(conn)
    _seed_blitz_questions(conn)
    _seed_roadmap_problems(conn)
    conn.close()
