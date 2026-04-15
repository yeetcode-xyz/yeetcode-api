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
        ("bounties",        "tags",                "TEXT"),
        ("bounties",        "difficulty_filter",   "TEXT"),
        ("bounty_progress", "baseline",            "INTEGER DEFAULT 0"),
        ("bounty_progress", "xp_awarded",          "INTEGER DEFAULT 0"),
        ("bounty_progress", "completed_at",        "TEXT DEFAULT NULL"),
        ("blitz_challenges", "time_limit_ms",       "INTEGER NOT NULL DEFAULT 60000"),
        ("duels",           "guest_challenger",     "INTEGER DEFAULT 0"),
        ("duel_invites",    "is_guest",             "INTEGER DEFAULT 0"),
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

# Testing drag_drop only — change to BLITZ_QUESTIONS_MCQ + DRAG_DROP_QUESTIONS for production
BLITZ_QUESTIONS = DRAG_DROP_QUESTIONS


def _seed_blitz_questions(conn):
    """Insert blitz questions. Clears and reseeds in DEBUG_MODE for easy dev iteration."""
    debug = os.getenv("DEBUG_MODE", "false").lower() == "true"
    count = conn.execute("SELECT COUNT(*) FROM blitz_questions").fetchone()[0]
    if count > 0 and not debug:
        return
    if debug and count > 0:
        conn.execute("DELETE FROM blitz_questions")
    for q in BLITZ_QUESTIONS:
        conn.execute(
            """INSERT INTO blitz_questions (category, difficulty, question, code, options, answer, explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [q["category"], q["difficulty"], q["question"], q.get("code"),
             q["options"], q["answer"], q.get("explanation")],
        )
    conn.commit()


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
    conn.close()
