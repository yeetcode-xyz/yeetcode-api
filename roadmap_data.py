"""
Canonical problem lists for Blind 75, NeetCode 150, and NeetCode 250.
Each problem has: category, title, slug (LeetCode titleSlug), difficulty, problem_number.
"""

BLIND75_PROBLEMS = [
    # ── Arrays & Hashing ─────────────────────────────────────────────────────────
    {"category": "Arrays & Hashing", "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy", "problem_number": 1},
    {"category": "Arrays & Hashing", "title": "Contains Duplicate", "slug": "contains-duplicate", "difficulty": "Easy", "problem_number": 217},
    {"category": "Arrays & Hashing", "title": "Valid Anagram", "slug": "valid-anagram", "difficulty": "Easy", "problem_number": 242},
    {"category": "Arrays & Hashing", "title": "Group Anagrams", "slug": "group-anagrams", "difficulty": "Medium", "problem_number": 49},
    {"category": "Arrays & Hashing", "title": "Top K Frequent Elements", "slug": "top-k-frequent-elements", "difficulty": "Medium", "problem_number": 347},
    {"category": "Arrays & Hashing", "title": "Encode and Decode Strings", "slug": "encode-and-decode-strings", "difficulty": "Medium", "problem_number": 271},
    {"category": "Arrays & Hashing", "title": "Product of Array Except Self", "slug": "product-of-array-except-self", "difficulty": "Medium", "problem_number": 238},
    {"category": "Arrays & Hashing", "title": "Longest Consecutive Sequence", "slug": "longest-consecutive-sequence", "difficulty": "Medium", "problem_number": 128},
    # ── Two Pointers ─────────────────────────────────────────────────────────────
    {"category": "Two Pointers", "title": "Valid Palindrome", "slug": "valid-palindrome", "difficulty": "Easy", "problem_number": 125},
    {"category": "Two Pointers", "title": "3Sum", "slug": "3sum", "difficulty": "Medium", "problem_number": 15},
    {"category": "Two Pointers", "title": "Container With Most Water", "slug": "container-with-most-water", "difficulty": "Medium", "problem_number": 11},
    # ── Sliding Window ───────────────────────────────────────────────────────────
    {"category": "Sliding Window", "title": "Best Time to Buy and Sell Stock", "slug": "best-time-to-buy-and-sell-stock", "difficulty": "Easy", "problem_number": 121},
    {"category": "Sliding Window", "title": "Longest Substring Without Repeating Characters", "slug": "longest-substring-without-repeating-characters", "difficulty": "Medium", "problem_number": 3},
    {"category": "Sliding Window", "title": "Longest Repeating Character Replacement", "slug": "longest-repeating-character-replacement", "difficulty": "Medium", "problem_number": 424},
    {"category": "Sliding Window", "title": "Minimum Window Substring", "slug": "minimum-window-substring", "difficulty": "Hard", "problem_number": 76},
    # ── Stack ────────────────────────────────────────────────────────────────────
    {"category": "Stack", "title": "Valid Parentheses", "slug": "valid-parentheses", "difficulty": "Easy", "problem_number": 20},
    # ── Binary Search ────────────────────────────────────────────────────────────
    {"category": "Binary Search", "title": "Find Minimum in Rotated Sorted Array", "slug": "find-minimum-in-rotated-sorted-array", "difficulty": "Medium", "problem_number": 153},
    {"category": "Binary Search", "title": "Search in Rotated Sorted Array", "slug": "search-in-rotated-sorted-array", "difficulty": "Medium", "problem_number": 33},
    # ── Linked List ──────────────────────────────────────────────────────────────
    {"category": "Linked List", "title": "Reverse Linked List", "slug": "reverse-linked-list", "difficulty": "Easy", "problem_number": 206},
    {"category": "Linked List", "title": "Merge Two Sorted Lists", "slug": "merge-two-sorted-lists", "difficulty": "Easy", "problem_number": 21},
    {"category": "Linked List", "title": "Linked List Cycle", "slug": "linked-list-cycle", "difficulty": "Easy", "problem_number": 141},
    {"category": "Linked List", "title": "Reorder List", "slug": "reorder-list", "difficulty": "Medium", "problem_number": 143},
    {"category": "Linked List", "title": "Remove Nth Node From End of List", "slug": "remove-nth-node-from-end-of-list", "difficulty": "Medium", "problem_number": 19},
    {"category": "Linked List", "title": "Merge k Sorted Lists", "slug": "merge-k-sorted-lists", "difficulty": "Hard", "problem_number": 23},
    # ── Trees ────────────────────────────────────────────────────────────────────
    {"category": "Trees", "title": "Invert Binary Tree", "slug": "invert-binary-tree", "difficulty": "Easy", "problem_number": 226},
    {"category": "Trees", "title": "Maximum Depth of Binary Tree", "slug": "maximum-depth-of-binary-tree", "difficulty": "Easy", "problem_number": 104},
    {"category": "Trees", "title": "Same Tree", "slug": "same-tree", "difficulty": "Easy", "problem_number": 100},
    {"category": "Trees", "title": "Subtree of Another Tree", "slug": "subtree-of-another-tree", "difficulty": "Easy", "problem_number": 572},
    {"category": "Trees", "title": "Lowest Common Ancestor of a Binary Search Tree", "slug": "lowest-common-ancestor-of-a-binary-search-tree", "difficulty": "Medium", "problem_number": 235},
    {"category": "Trees", "title": "Binary Tree Level Order Traversal", "slug": "binary-tree-level-order-traversal", "difficulty": "Medium", "problem_number": 102},
    {"category": "Trees", "title": "Validate Binary Search Tree", "slug": "validate-binary-search-tree", "difficulty": "Medium", "problem_number": 98},
    {"category": "Trees", "title": "Kth Smallest Element in a BST", "slug": "kth-smallest-element-in-a-bst", "difficulty": "Medium", "problem_number": 230},
    {"category": "Trees", "title": "Construct Binary Tree from Preorder and Inorder Traversal", "slug": "construct-binary-tree-from-preorder-and-inorder-traversal", "difficulty": "Medium", "problem_number": 105},
    {"category": "Trees", "title": "Binary Tree Maximum Path Sum", "slug": "binary-tree-maximum-path-sum", "difficulty": "Hard", "problem_number": 124},
    {"category": "Trees", "title": "Serialize and Deserialize Binary Tree", "slug": "serialize-and-deserialize-binary-tree", "difficulty": "Hard", "problem_number": 297},
    # ── Tries ────────────────────────────────────────────────────────────────────
    {"category": "Tries", "title": "Implement Trie (Prefix Tree)", "slug": "implement-trie-prefix-tree", "difficulty": "Medium", "problem_number": 208},
    {"category": "Tries", "title": "Design Add and Search Words Data Structure", "slug": "design-add-and-search-words-data-structure", "difficulty": "Medium", "problem_number": 211},
    {"category": "Tries", "title": "Word Search II", "slug": "word-search-ii", "difficulty": "Hard", "problem_number": 212},
    # ── Heap / Priority Queue ────────────────────────────────────────────────────
    {"category": "Heap / Priority Queue", "title": "Find Median from Data Stream", "slug": "find-median-from-data-stream", "difficulty": "Hard", "problem_number": 295},
    # ── Backtracking ─────────────────────────────────────────────────────────────
    {"category": "Backtracking", "title": "Combination Sum", "slug": "combination-sum", "difficulty": "Medium", "problem_number": 39},
    {"category": "Backtracking", "title": "Word Search", "slug": "word-search", "difficulty": "Medium", "problem_number": 79},
    # ── Graphs ───────────────────────────────────────────────────────────────────
    {"category": "Graphs", "title": "Number of Islands", "slug": "number-of-islands", "difficulty": "Medium", "problem_number": 200},
    {"category": "Graphs", "title": "Clone Graph", "slug": "clone-graph", "difficulty": "Medium", "problem_number": 133},
    {"category": "Graphs", "title": "Pacific Atlantic Water Flow", "slug": "pacific-atlantic-water-flow", "difficulty": "Medium", "problem_number": 417},
    {"category": "Graphs", "title": "Course Schedule", "slug": "course-schedule", "difficulty": "Medium", "problem_number": 207},
    {"category": "Graphs", "title": "Number of Connected Components in an Undirected Graph", "slug": "number-of-connected-components-in-an-undirected-graph", "difficulty": "Medium", "problem_number": 323},
    {"category": "Graphs", "title": "Graph Valid Tree", "slug": "graph-valid-tree", "difficulty": "Medium", "problem_number": 261},
    # ── Advanced Graphs ──────────────────────────────────────────────────────────
    {"category": "Advanced Graphs", "title": "Alien Dictionary", "slug": "alien-dictionary", "difficulty": "Hard", "problem_number": 269},
    # ── 1-D DP ───────────────────────────────────────────────────────────────────
    {"category": "1-D DP", "title": "Climbing Stairs", "slug": "climbing-stairs", "difficulty": "Easy", "problem_number": 70},
    {"category": "1-D DP", "title": "House Robber", "slug": "house-robber", "difficulty": "Medium", "problem_number": 198},
    {"category": "1-D DP", "title": "House Robber II", "slug": "house-robber-ii", "difficulty": "Medium", "problem_number": 213},
    {"category": "1-D DP", "title": "Longest Palindromic Substring", "slug": "longest-palindromic-substring", "difficulty": "Medium", "problem_number": 5},
    {"category": "1-D DP", "title": "Palindromic Substrings", "slug": "palindromic-substrings", "difficulty": "Medium", "problem_number": 647},
    {"category": "1-D DP", "title": "Decode Ways", "slug": "decode-ways", "difficulty": "Medium", "problem_number": 91},
    {"category": "1-D DP", "title": "Coin Change", "slug": "coin-change", "difficulty": "Medium", "problem_number": 322},
    {"category": "1-D DP", "title": "Maximum Product Subarray", "slug": "maximum-product-subarray", "difficulty": "Medium", "problem_number": 152},
    {"category": "1-D DP", "title": "Word Break", "slug": "word-break", "difficulty": "Medium", "problem_number": 139},
    {"category": "1-D DP", "title": "Longest Increasing Subsequence", "slug": "longest-increasing-subsequence", "difficulty": "Medium", "problem_number": 300},
    # ── 2-D DP ───────────────────────────────────────────────────────────────────
    {"category": "2-D DP", "title": "Unique Paths", "slug": "unique-paths", "difficulty": "Medium", "problem_number": 62},
    {"category": "2-D DP", "title": "Longest Common Subsequence", "slug": "longest-common-subsequence", "difficulty": "Medium", "problem_number": 1143},
    # ── Greedy ───────────────────────────────────────────────────────────────────
    {"category": "Greedy", "title": "Maximum Subarray", "slug": "maximum-subarray", "difficulty": "Medium", "problem_number": 53},
    {"category": "Greedy", "title": "Jump Game", "slug": "jump-game", "difficulty": "Medium", "problem_number": 55},
    # ── Intervals ────────────────────────────────────────────────────────────────
    {"category": "Intervals", "title": "Insert Interval", "slug": "insert-interval", "difficulty": "Medium", "problem_number": 57},
    {"category": "Intervals", "title": "Merge Intervals", "slug": "merge-intervals", "difficulty": "Medium", "problem_number": 56},
    {"category": "Intervals", "title": "Non-overlapping Intervals", "slug": "non-overlapping-intervals", "difficulty": "Medium", "problem_number": 435},
    {"category": "Intervals", "title": "Meeting Rooms", "slug": "meeting-rooms", "difficulty": "Easy", "problem_number": 252},
    {"category": "Intervals", "title": "Meeting Rooms II", "slug": "meeting-rooms-ii", "difficulty": "Medium", "problem_number": 253},
    # ── Math & Geometry ──────────────────────────────────────────────────────────
    {"category": "Math & Geometry", "title": "Rotate Image", "slug": "rotate-image", "difficulty": "Medium", "problem_number": 48},
    {"category": "Math & Geometry", "title": "Spiral Matrix", "slug": "spiral-matrix", "difficulty": "Medium", "problem_number": 54},
    {"category": "Math & Geometry", "title": "Set Matrix Zeroes", "slug": "set-matrix-zeroes", "difficulty": "Medium", "problem_number": 73},
    # ── Bit Manipulation ─────────────────────────────────────────────────────────
    {"category": "Bit Manipulation", "title": "Number of 1 Bits", "slug": "number-of-1-bits", "difficulty": "Easy", "problem_number": 191},
    {"category": "Bit Manipulation", "title": "Counting Bits", "slug": "counting-bits", "difficulty": "Easy", "problem_number": 338},
    {"category": "Bit Manipulation", "title": "Reverse Bits", "slug": "reverse-bits", "difficulty": "Easy", "problem_number": 190},
    {"category": "Bit Manipulation", "title": "Missing Number", "slug": "missing-number", "difficulty": "Easy", "problem_number": 268},
    {"category": "Bit Manipulation", "title": "Sum of Two Integers", "slug": "sum-of-two-integers", "difficulty": "Medium", "problem_number": 371},
]

NEETCODE150_PROBLEMS = [
    # ── Arrays & Hashing ─────────────────────────────────────────────────────────
    {"category": "Arrays & Hashing", "title": "Contains Duplicate", "slug": "contains-duplicate", "difficulty": "Easy", "problem_number": 217},
    {"category": "Arrays & Hashing", "title": "Valid Anagram", "slug": "valid-anagram", "difficulty": "Easy", "problem_number": 242},
    {"category": "Arrays & Hashing", "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy", "problem_number": 1},
    {"category": "Arrays & Hashing", "title": "Group Anagrams", "slug": "group-anagrams", "difficulty": "Medium", "problem_number": 49},
    {"category": "Arrays & Hashing", "title": "Top K Frequent Elements", "slug": "top-k-frequent-elements", "difficulty": "Medium", "problem_number": 347},
    {"category": "Arrays & Hashing", "title": "Encode and Decode Strings", "slug": "encode-and-decode-strings", "difficulty": "Medium", "problem_number": 271},
    {"category": "Arrays & Hashing", "title": "Product of Array Except Self", "slug": "product-of-array-except-self", "difficulty": "Medium", "problem_number": 238},
    {"category": "Arrays & Hashing", "title": "Valid Sudoku", "slug": "valid-sudoku", "difficulty": "Medium", "problem_number": 36},
    {"category": "Arrays & Hashing", "title": "Longest Consecutive Sequence", "slug": "longest-consecutive-sequence", "difficulty": "Medium", "problem_number": 128},
    # ── Two Pointers ─────────────────────────────────────────────────────────────
    {"category": "Two Pointers", "title": "Valid Palindrome", "slug": "valid-palindrome", "difficulty": "Easy", "problem_number": 125},
    {"category": "Two Pointers", "title": "Two Sum II - Input Array Is Sorted", "slug": "two-sum-ii-input-array-is-sorted", "difficulty": "Medium", "problem_number": 167},
    {"category": "Two Pointers", "title": "3Sum", "slug": "3sum", "difficulty": "Medium", "problem_number": 15},
    {"category": "Two Pointers", "title": "Container With Most Water", "slug": "container-with-most-water", "difficulty": "Medium", "problem_number": 11},
    {"category": "Two Pointers", "title": "Trapping Rain Water", "slug": "trapping-rain-water", "difficulty": "Hard", "problem_number": 42},
    # ── Sliding Window ───────────────────────────────────────────────────────────
    {"category": "Sliding Window", "title": "Best Time to Buy and Sell Stock", "slug": "best-time-to-buy-and-sell-stock", "difficulty": "Easy", "problem_number": 121},
    {"category": "Sliding Window", "title": "Longest Substring Without Repeating Characters", "slug": "longest-substring-without-repeating-characters", "difficulty": "Medium", "problem_number": 3},
    {"category": "Sliding Window", "title": "Longest Repeating Character Replacement", "slug": "longest-repeating-character-replacement", "difficulty": "Medium", "problem_number": 424},
    {"category": "Sliding Window", "title": "Permutation in String", "slug": "permutation-in-string", "difficulty": "Medium", "problem_number": 567},
    {"category": "Sliding Window", "title": "Minimum Window Substring", "slug": "minimum-window-substring", "difficulty": "Hard", "problem_number": 76},
    {"category": "Sliding Window", "title": "Sliding Window Maximum", "slug": "sliding-window-maximum", "difficulty": "Hard", "problem_number": 239},
    # ── Stack ────────────────────────────────────────────────────────────────────
    {"category": "Stack", "title": "Valid Parentheses", "slug": "valid-parentheses", "difficulty": "Easy", "problem_number": 20},
    {"category": "Stack", "title": "Min Stack", "slug": "min-stack", "difficulty": "Medium", "problem_number": 155},
    {"category": "Stack", "title": "Evaluate Reverse Polish Notation", "slug": "evaluate-reverse-polish-notation", "difficulty": "Medium", "problem_number": 150},
    {"category": "Stack", "title": "Generate Parentheses", "slug": "generate-parentheses", "difficulty": "Medium", "problem_number": 22},
    {"category": "Stack", "title": "Daily Temperatures", "slug": "daily-temperatures", "difficulty": "Medium", "problem_number": 739},
    {"category": "Stack", "title": "Car Fleet", "slug": "car-fleet", "difficulty": "Medium", "problem_number": 853},
    {"category": "Stack", "title": "Largest Rectangle in Histogram", "slug": "largest-rectangle-in-histogram", "difficulty": "Hard", "problem_number": 84},
    # ── Binary Search ────────────────────────────────────────────────────────────
    {"category": "Binary Search", "title": "Binary Search", "slug": "binary-search", "difficulty": "Easy", "problem_number": 704},
    {"category": "Binary Search", "title": "Search a 2D Matrix", "slug": "search-a-2d-matrix", "difficulty": "Medium", "problem_number": 74},
    {"category": "Binary Search", "title": "Koko Eating Bananas", "slug": "koko-eating-bananas", "difficulty": "Medium", "problem_number": 875},
    {"category": "Binary Search", "title": "Find Minimum in Rotated Sorted Array", "slug": "find-minimum-in-rotated-sorted-array", "difficulty": "Medium", "problem_number": 153},
    {"category": "Binary Search", "title": "Search in Rotated Sorted Array", "slug": "search-in-rotated-sorted-array", "difficulty": "Medium", "problem_number": 33},
    {"category": "Binary Search", "title": "Time Based Key-Value Store", "slug": "time-based-key-value-store", "difficulty": "Medium", "problem_number": 981},
    {"category": "Binary Search", "title": "Median of Two Sorted Arrays", "slug": "median-of-two-sorted-arrays", "difficulty": "Hard", "problem_number": 4},
    # ── Linked List ──────────────────────────────────────────────────────────────
    {"category": "Linked List", "title": "Reverse Linked List", "slug": "reverse-linked-list", "difficulty": "Easy", "problem_number": 206},
    {"category": "Linked List", "title": "Merge Two Sorted Lists", "slug": "merge-two-sorted-lists", "difficulty": "Easy", "problem_number": 21},
    {"category": "Linked List", "title": "Linked List Cycle", "slug": "linked-list-cycle", "difficulty": "Easy", "problem_number": 141},
    {"category": "Linked List", "title": "Reorder List", "slug": "reorder-list", "difficulty": "Medium", "problem_number": 143},
    {"category": "Linked List", "title": "Remove Nth Node From End of List", "slug": "remove-nth-node-from-end-of-list", "difficulty": "Medium", "problem_number": 19},
    {"category": "Linked List", "title": "Copy List with Random Pointer", "slug": "copy-list-with-random-pointer", "difficulty": "Medium", "problem_number": 138},
    {"category": "Linked List", "title": "Add Two Numbers", "slug": "add-two-numbers", "difficulty": "Medium", "problem_number": 2},
    {"category": "Linked List", "title": "Find the Duplicate Number", "slug": "find-the-duplicate-number", "difficulty": "Medium", "problem_number": 287},
    {"category": "Linked List", "title": "LRU Cache", "slug": "lru-cache", "difficulty": "Medium", "problem_number": 146},
    {"category": "Linked List", "title": "Merge k Sorted Lists", "slug": "merge-k-sorted-lists", "difficulty": "Hard", "problem_number": 23},
    {"category": "Linked List", "title": "Reverse Nodes in k-Group", "slug": "reverse-nodes-in-k-group", "difficulty": "Hard", "problem_number": 25},
    # ── Trees ────────────────────────────────────────────────────────────────────
    {"category": "Trees", "title": "Invert Binary Tree", "slug": "invert-binary-tree", "difficulty": "Easy", "problem_number": 226},
    {"category": "Trees", "title": "Maximum Depth of Binary Tree", "slug": "maximum-depth-of-binary-tree", "difficulty": "Easy", "problem_number": 104},
    {"category": "Trees", "title": "Diameter of Binary Tree", "slug": "diameter-of-binary-tree", "difficulty": "Easy", "problem_number": 543},
    {"category": "Trees", "title": "Balanced Binary Tree", "slug": "balanced-binary-tree", "difficulty": "Easy", "problem_number": 110},
    {"category": "Trees", "title": "Same Tree", "slug": "same-tree", "difficulty": "Easy", "problem_number": 100},
    {"category": "Trees", "title": "Subtree of Another Tree", "slug": "subtree-of-another-tree", "difficulty": "Easy", "problem_number": 572},
    {"category": "Trees", "title": "Lowest Common Ancestor of a Binary Search Tree", "slug": "lowest-common-ancestor-of-a-binary-search-tree", "difficulty": "Medium", "problem_number": 235},
    {"category": "Trees", "title": "Binary Tree Level Order Traversal", "slug": "binary-tree-level-order-traversal", "difficulty": "Medium", "problem_number": 102},
    {"category": "Trees", "title": "Binary Tree Right Side View", "slug": "binary-tree-right-side-view", "difficulty": "Medium", "problem_number": 199},
    {"category": "Trees", "title": "Count Good Nodes in Binary Tree", "slug": "count-good-nodes-in-binary-tree", "difficulty": "Medium", "problem_number": 1448},
    {"category": "Trees", "title": "Validate Binary Search Tree", "slug": "validate-binary-search-tree", "difficulty": "Medium", "problem_number": 98},
    {"category": "Trees", "title": "Kth Smallest Element in a BST", "slug": "kth-smallest-element-in-a-bst", "difficulty": "Medium", "problem_number": 230},
    {"category": "Trees", "title": "Construct Binary Tree from Preorder and Inorder Traversal", "slug": "construct-binary-tree-from-preorder-and-inorder-traversal", "difficulty": "Medium", "problem_number": 105},
    {"category": "Trees", "title": "Binary Tree Maximum Path Sum", "slug": "binary-tree-maximum-path-sum", "difficulty": "Hard", "problem_number": 124},
    {"category": "Trees", "title": "Serialize and Deserialize Binary Tree", "slug": "serialize-and-deserialize-binary-tree", "difficulty": "Hard", "problem_number": 297},
    # ── Tries ────────────────────────────────────────────────────────────────────
    {"category": "Tries", "title": "Implement Trie (Prefix Tree)", "slug": "implement-trie-prefix-tree", "difficulty": "Medium", "problem_number": 208},
    {"category": "Tries", "title": "Design Add and Search Words Data Structure", "slug": "design-add-and-search-words-data-structure", "difficulty": "Medium", "problem_number": 211},
    {"category": "Tries", "title": "Word Search II", "slug": "word-search-ii", "difficulty": "Hard", "problem_number": 212},
    # ── Heap / Priority Queue ────────────────────────────────────────────────────
    {"category": "Heap / Priority Queue", "title": "Kth Largest Element in a Stream", "slug": "kth-largest-element-in-a-stream", "difficulty": "Easy", "problem_number": 703},
    {"category": "Heap / Priority Queue", "title": "Last Stone Weight", "slug": "last-stone-weight", "difficulty": "Easy", "problem_number": 1046},
    {"category": "Heap / Priority Queue", "title": "K Closest Points to Origin", "slug": "k-closest-points-to-origin", "difficulty": "Medium", "problem_number": 973},
    {"category": "Heap / Priority Queue", "title": "Kth Largest Element in an Array", "slug": "kth-largest-element-in-an-array", "difficulty": "Medium", "problem_number": 215},
    {"category": "Heap / Priority Queue", "title": "Task Scheduler", "slug": "task-scheduler", "difficulty": "Medium", "problem_number": 621},
    {"category": "Heap / Priority Queue", "title": "Design Twitter", "slug": "design-twitter", "difficulty": "Medium", "problem_number": 355},
    {"category": "Heap / Priority Queue", "title": "Find Median from Data Stream", "slug": "find-median-from-data-stream", "difficulty": "Hard", "problem_number": 295},
    # ── Backtracking ─────────────────────────────────────────────────────────────
    {"category": "Backtracking", "title": "Subsets", "slug": "subsets", "difficulty": "Medium", "problem_number": 78},
    {"category": "Backtracking", "title": "Combination Sum", "slug": "combination-sum", "difficulty": "Medium", "problem_number": 39},
    {"category": "Backtracking", "title": "Combination Sum II", "slug": "combination-sum-ii", "difficulty": "Medium", "problem_number": 40},
    {"category": "Backtracking", "title": "Permutations", "slug": "permutations", "difficulty": "Medium", "problem_number": 46},
    {"category": "Backtracking", "title": "Subsets II", "slug": "subsets-ii", "difficulty": "Medium", "problem_number": 90},
    {"category": "Backtracking", "title": "Word Search", "slug": "word-search", "difficulty": "Medium", "problem_number": 79},
    {"category": "Backtracking", "title": "Palindrome Partitioning", "slug": "palindrome-partitioning", "difficulty": "Medium", "problem_number": 131},
    {"category": "Backtracking", "title": "Letter Combinations of a Phone Number", "slug": "letter-combinations-of-a-phone-number", "difficulty": "Medium", "problem_number": 17},
    {"category": "Backtracking", "title": "N-Queens", "slug": "n-queens", "difficulty": "Hard", "problem_number": 51},
    # ── Graphs ───────────────────────────────────────────────────────────────────
    {"category": "Graphs", "title": "Number of Islands", "slug": "number-of-islands", "difficulty": "Medium", "problem_number": 200},
    {"category": "Graphs", "title": "Clone Graph", "slug": "clone-graph", "difficulty": "Medium", "problem_number": 133},
    {"category": "Graphs", "title": "Max Area of Island", "slug": "max-area-of-island", "difficulty": "Medium", "problem_number": 695},
    {"category": "Graphs", "title": "Pacific Atlantic Water Flow", "slug": "pacific-atlantic-water-flow", "difficulty": "Medium", "problem_number": 417},
    {"category": "Graphs", "title": "Surrounded Regions", "slug": "surrounded-regions", "difficulty": "Medium", "problem_number": 130},
    {"category": "Graphs", "title": "Rotting Oranges", "slug": "rotting-oranges", "difficulty": "Medium", "problem_number": 994},
    {"category": "Graphs", "title": "Walls and Gates", "slug": "walls-and-gates", "difficulty": "Medium", "problem_number": 286},
    {"category": "Graphs", "title": "Course Schedule", "slug": "course-schedule", "difficulty": "Medium", "problem_number": 207},
    {"category": "Graphs", "title": "Course Schedule II", "slug": "course-schedule-ii", "difficulty": "Medium", "problem_number": 210},
    {"category": "Graphs", "title": "Redundant Connection", "slug": "redundant-connection", "difficulty": "Medium", "problem_number": 684},
    {"category": "Graphs", "title": "Number of Connected Components in an Undirected Graph", "slug": "number-of-connected-components-in-an-undirected-graph", "difficulty": "Medium", "problem_number": 323},
    {"category": "Graphs", "title": "Graph Valid Tree", "slug": "graph-valid-tree", "difficulty": "Medium", "problem_number": 261},
    {"category": "Graphs", "title": "Word Ladder", "slug": "word-ladder", "difficulty": "Hard", "problem_number": 127},
    # ── Advanced Graphs ──────────────────────────────────────────────────────────
    {"category": "Advanced Graphs", "title": "Reconstruct Itinerary", "slug": "reconstruct-itinerary", "difficulty": "Hard", "problem_number": 332},
    {"category": "Advanced Graphs", "title": "Min Cost to Connect All Points", "slug": "min-cost-to-connect-all-points", "difficulty": "Medium", "problem_number": 1584},
    {"category": "Advanced Graphs", "title": "Network Delay Time", "slug": "network-delay-time", "difficulty": "Medium", "problem_number": 743},
    {"category": "Advanced Graphs", "title": "Swim in Rising Water", "slug": "swim-in-rising-water", "difficulty": "Hard", "problem_number": 778},
    {"category": "Advanced Graphs", "title": "Alien Dictionary", "slug": "alien-dictionary", "difficulty": "Hard", "problem_number": 269},
    {"category": "Advanced Graphs", "title": "Cheapest Flights Within K Stops", "slug": "cheapest-flights-within-k-stops", "difficulty": "Medium", "problem_number": 787},
    # ── 1-D DP ───────────────────────────────────────────────────────────────────
    {"category": "1-D DP", "title": "Climbing Stairs", "slug": "climbing-stairs", "difficulty": "Easy", "problem_number": 70},
    {"category": "1-D DP", "title": "Min Cost Climbing Stairs", "slug": "min-cost-climbing-stairs", "difficulty": "Easy", "problem_number": 746},
    {"category": "1-D DP", "title": "House Robber", "slug": "house-robber", "difficulty": "Medium", "problem_number": 198},
    {"category": "1-D DP", "title": "House Robber II", "slug": "house-robber-ii", "difficulty": "Medium", "problem_number": 213},
    {"category": "1-D DP", "title": "Longest Palindromic Substring", "slug": "longest-palindromic-substring", "difficulty": "Medium", "problem_number": 5},
    {"category": "1-D DP", "title": "Palindromic Substrings", "slug": "palindromic-substrings", "difficulty": "Medium", "problem_number": 647},
    {"category": "1-D DP", "title": "Decode Ways", "slug": "decode-ways", "difficulty": "Medium", "problem_number": 91},
    {"category": "1-D DP", "title": "Coin Change", "slug": "coin-change", "difficulty": "Medium", "problem_number": 322},
    {"category": "1-D DP", "title": "Maximum Product Subarray", "slug": "maximum-product-subarray", "difficulty": "Medium", "problem_number": 152},
    {"category": "1-D DP", "title": "Word Break", "slug": "word-break", "difficulty": "Medium", "problem_number": 139},
    {"category": "1-D DP", "title": "Longest Increasing Subsequence", "slug": "longest-increasing-subsequence", "difficulty": "Medium", "problem_number": 300},
    {"category": "1-D DP", "title": "Partition Equal Subset Sum", "slug": "partition-equal-subset-sum", "difficulty": "Medium", "problem_number": 416},
    # ── 2-D DP ───────────────────────────────────────────────────────────────────
    {"category": "2-D DP", "title": "Unique Paths", "slug": "unique-paths", "difficulty": "Medium", "problem_number": 62},
    {"category": "2-D DP", "title": "Longest Common Subsequence", "slug": "longest-common-subsequence", "difficulty": "Medium", "problem_number": 1143},
    {"category": "2-D DP", "title": "Best Time to Buy and Sell Stock with Cooldown", "slug": "best-time-to-buy-and-sell-stock-with-cooldown", "difficulty": "Medium", "problem_number": 309},
    {"category": "2-D DP", "title": "Coin Change II", "slug": "coin-change-ii", "difficulty": "Medium", "problem_number": 518},
    {"category": "2-D DP", "title": "Target Sum", "slug": "target-sum", "difficulty": "Medium", "problem_number": 494},
    {"category": "2-D DP", "title": "Interleaving String", "slug": "interleaving-string", "difficulty": "Medium", "problem_number": 97},
    {"category": "2-D DP", "title": "Longest Increasing Path in a Matrix", "slug": "longest-increasing-path-in-a-matrix", "difficulty": "Hard", "problem_number": 329},
    {"category": "2-D DP", "title": "Distinct Subsequences", "slug": "distinct-subsequences", "difficulty": "Hard", "problem_number": 115},
    {"category": "2-D DP", "title": "Edit Distance", "slug": "edit-distance", "difficulty": "Medium", "problem_number": 72},
    {"category": "2-D DP", "title": "Burst Balloons", "slug": "burst-balloons", "difficulty": "Hard", "problem_number": 312},
    {"category": "2-D DP", "title": "Regular Expression Matching", "slug": "regular-expression-matching", "difficulty": "Hard", "problem_number": 10},
    # ── Greedy ───────────────────────────────────────────────────────────────────
    {"category": "Greedy", "title": "Maximum Subarray", "slug": "maximum-subarray", "difficulty": "Medium", "problem_number": 53},
    {"category": "Greedy", "title": "Jump Game", "slug": "jump-game", "difficulty": "Medium", "problem_number": 55},
    {"category": "Greedy", "title": "Jump Game II", "slug": "jump-game-ii", "difficulty": "Medium", "problem_number": 45},
    {"category": "Greedy", "title": "Gas Station", "slug": "gas-station", "difficulty": "Medium", "problem_number": 134},
    {"category": "Greedy", "title": "Hand of Straights", "slug": "hand-of-straights", "difficulty": "Medium", "problem_number": 846},
    {"category": "Greedy", "title": "Merge Triplets to Form Target Triplet", "slug": "merge-triplets-to-form-target-triplet", "difficulty": "Medium", "problem_number": 1899},
    {"category": "Greedy", "title": "Partition Labels", "slug": "partition-labels", "difficulty": "Medium", "problem_number": 763},
    {"category": "Greedy", "title": "Valid Parenthesis String", "slug": "valid-parenthesis-string", "difficulty": "Medium", "problem_number": 678},
    # ── Intervals ────────────────────────────────────────────────────────────────
    {"category": "Intervals", "title": "Insert Interval", "slug": "insert-interval", "difficulty": "Medium", "problem_number": 57},
    {"category": "Intervals", "title": "Merge Intervals", "slug": "merge-intervals", "difficulty": "Medium", "problem_number": 56},
    {"category": "Intervals", "title": "Non-overlapping Intervals", "slug": "non-overlapping-intervals", "difficulty": "Medium", "problem_number": 435},
    {"category": "Intervals", "title": "Meeting Rooms", "slug": "meeting-rooms", "difficulty": "Easy", "problem_number": 252},
    {"category": "Intervals", "title": "Meeting Rooms II", "slug": "meeting-rooms-ii", "difficulty": "Medium", "problem_number": 253},
    {"category": "Intervals", "title": "Minimum Interval to Include Each Query", "slug": "minimum-interval-to-include-each-query", "difficulty": "Hard", "problem_number": 1851},
    # ── Math & Geometry ──────────────────────────────────────────────────────────
    {"category": "Math & Geometry", "title": "Rotate Image", "slug": "rotate-image", "difficulty": "Medium", "problem_number": 48},
    {"category": "Math & Geometry", "title": "Spiral Matrix", "slug": "spiral-matrix", "difficulty": "Medium", "problem_number": 54},
    {"category": "Math & Geometry", "title": "Set Matrix Zeroes", "slug": "set-matrix-zeroes", "difficulty": "Medium", "problem_number": 73},
    {"category": "Math & Geometry", "title": "Happy Number", "slug": "happy-number", "difficulty": "Easy", "problem_number": 202},
    {"category": "Math & Geometry", "title": "Plus One", "slug": "plus-one", "difficulty": "Easy", "problem_number": 66},
    {"category": "Math & Geometry", "title": "Pow(x, n)", "slug": "powx-n", "difficulty": "Medium", "problem_number": 50},
    {"category": "Math & Geometry", "title": "Multiply Strings", "slug": "multiply-strings", "difficulty": "Medium", "problem_number": 43},
    {"category": "Math & Geometry", "title": "Detect Squares", "slug": "detect-squares", "difficulty": "Medium", "problem_number": 2013},
    # ── Bit Manipulation ─────────────────────────────────────────────────────────
    {"category": "Bit Manipulation", "title": "Single Number", "slug": "single-number", "difficulty": "Easy", "problem_number": 136},
    {"category": "Bit Manipulation", "title": "Number of 1 Bits", "slug": "number-of-1-bits", "difficulty": "Easy", "problem_number": 191},
    {"category": "Bit Manipulation", "title": "Counting Bits", "slug": "counting-bits", "difficulty": "Easy", "problem_number": 338},
    {"category": "Bit Manipulation", "title": "Reverse Bits", "slug": "reverse-bits", "difficulty": "Easy", "problem_number": 190},
    {"category": "Bit Manipulation", "title": "Missing Number", "slug": "missing-number", "difficulty": "Easy", "problem_number": 268},
    {"category": "Bit Manipulation", "title": "Sum of Two Integers", "slug": "sum-of-two-integers", "difficulty": "Medium", "problem_number": 371},
    {"category": "Bit Manipulation", "title": "Reverse Integer", "slug": "reverse-integer", "difficulty": "Medium", "problem_number": 7},
]

# NeetCode 250 = NeetCode 150 + 100 additional problems
# Start with all 150, then add the extras
NEETCODE250_EXTRAS = [
    # ── Arrays & Hashing (extras) ────────────────────────────────────────────────
    {"category": "Arrays & Hashing", "title": "Concatenation of Array", "slug": "concatenation-of-array", "difficulty": "Easy", "problem_number": 1929},
    {"category": "Arrays & Hashing", "title": "Replace Elements with Greatest Element on Right Side", "slug": "replace-elements-with-greatest-element-on-right-side", "difficulty": "Easy", "problem_number": 1299},
    {"category": "Arrays & Hashing", "title": "Is Subsequence", "slug": "is-subsequence", "difficulty": "Easy", "problem_number": 392},
    {"category": "Arrays & Hashing", "title": "Length of Last Word", "slug": "length-of-last-word", "difficulty": "Easy", "problem_number": 58},
    {"category": "Arrays & Hashing", "title": "Longest Common Prefix", "slug": "longest-common-prefix", "difficulty": "Easy", "problem_number": 14},
    {"category": "Arrays & Hashing", "title": "Pascals Triangle", "slug": "pascals-triangle", "difficulty": "Easy", "problem_number": 118},
    {"category": "Arrays & Hashing", "title": "Remove Element", "slug": "remove-element", "difficulty": "Easy", "problem_number": 27},
    {"category": "Arrays & Hashing", "title": "Unique Email Addresses", "slug": "unique-email-addresses", "difficulty": "Easy", "problem_number": 929},
    {"category": "Arrays & Hashing", "title": "Majority Element", "slug": "majority-element", "difficulty": "Easy", "problem_number": 169},
    {"category": "Arrays & Hashing", "title": "Next Greater Element I", "slug": "next-greater-element-i", "difficulty": "Easy", "problem_number": 496},
    {"category": "Arrays & Hashing", "title": "Sort Colors", "slug": "sort-colors", "difficulty": "Medium", "problem_number": 75},
    {"category": "Arrays & Hashing", "title": "Brick Wall", "slug": "brick-wall", "difficulty": "Medium", "problem_number": 554},
    {"category": "Arrays & Hashing", "title": "Best Time to Buy and Sell Stock II", "slug": "best-time-to-buy-and-sell-stock-ii", "difficulty": "Medium", "problem_number": 122},
    {"category": "Arrays & Hashing", "title": "Subarray Sum Equals K", "slug": "subarray-sum-equals-k", "difficulty": "Medium", "problem_number": 560},
    {"category": "Arrays & Hashing", "title": "Non-decreasing Array", "slug": "non-decreasing-array", "difficulty": "Medium", "problem_number": 665},
    # ── Two Pointers (extras) ────────────────────────────────────────────────────
    {"category": "Two Pointers", "title": "Remove Duplicates from Sorted Array", "slug": "remove-duplicates-from-sorted-array", "difficulty": "Easy", "problem_number": 26},
    {"category": "Two Pointers", "title": "Move Zeroes", "slug": "move-zeroes", "difficulty": "Easy", "problem_number": 283},
    {"category": "Two Pointers", "title": "4Sum", "slug": "4sum", "difficulty": "Medium", "problem_number": 18},
    {"category": "Two Pointers", "title": "Rotate Array", "slug": "rotate-array", "difficulty": "Medium", "problem_number": 189},
    {"category": "Two Pointers", "title": "Number of Subsequences That Satisfy the Given Sum Condition", "slug": "number-of-subsequences-that-satisfy-the-given-sum-condition", "difficulty": "Medium", "problem_number": 1498},
    # ── Sliding Window (extras) ──────────────────────────────────────────────────
    {"category": "Sliding Window", "title": "Contains Duplicate II", "slug": "contains-duplicate-ii", "difficulty": "Easy", "problem_number": 219},
    {"category": "Sliding Window", "title": "Number of Sub-arrays of Size K and Average Greater than or Equal to Threshold", "slug": "number-of-sub-arrays-of-size-k-and-average-greater-than-or-equal-to-threshold", "difficulty": "Medium", "problem_number": 1343},
    {"category": "Sliding Window", "title": "Minimum Size Subarray Sum", "slug": "minimum-size-subarray-sum", "difficulty": "Medium", "problem_number": 209},
    {"category": "Sliding Window", "title": "Frequency of the Most Frequent Element", "slug": "frequency-of-the-most-frequent-element", "difficulty": "Medium", "problem_number": 1838},
    # ── Stack (extras) ───────────────────────────────────────────────────────────
    {"category": "Stack", "title": "Baseball Game", "slug": "baseball-game", "difficulty": "Easy", "problem_number": 682},
    {"category": "Stack", "title": "Implement Stack using Queues", "slug": "implement-stack-using-queues", "difficulty": "Easy", "problem_number": 225},
    {"category": "Stack", "title": "Removing Stars From a String", "slug": "removing-stars-from-a-string", "difficulty": "Medium", "problem_number": 2390},
    {"category": "Stack", "title": "Asteroid Collision", "slug": "asteroid-collision", "difficulty": "Medium", "problem_number": 735},
    {"category": "Stack", "title": "Online Stock Span", "slug": "online-stock-span", "difficulty": "Medium", "problem_number": 901},
    {"category": "Stack", "title": "Maximum Frequency Stack", "slug": "maximum-frequency-stack", "difficulty": "Hard", "problem_number": 895},
    # ── Binary Search (extras) ───────────────────────────────────────────────────
    {"category": "Binary Search", "title": "Search Insert Position", "slug": "search-insert-position", "difficulty": "Easy", "problem_number": 35},
    {"category": "Binary Search", "title": "Guess Number Higher or Lower", "slug": "guess-number-higher-or-lower", "difficulty": "Easy", "problem_number": 374},
    {"category": "Binary Search", "title": "Successful Pairs of Spells and Potions", "slug": "successful-pairs-of-spells-and-potions", "difficulty": "Medium", "problem_number": 2300},
    {"category": "Binary Search", "title": "Find Peak Element", "slug": "find-peak-element", "difficulty": "Medium", "problem_number": 162},
    {"category": "Binary Search", "title": "Capacity To Ship Packages Within D Days", "slug": "capacity-to-ship-packages-within-d-days", "difficulty": "Medium", "problem_number": 1011},
    {"category": "Binary Search", "title": "Split Array Largest Sum", "slug": "split-array-largest-sum", "difficulty": "Hard", "problem_number": 410},
    # ── Linked List (extras) ─────────────────────────────────────────────────────
    {"category": "Linked List", "title": "Middle of the Linked List", "slug": "middle-of-the-linked-list", "difficulty": "Easy", "problem_number": 876},
    {"category": "Linked List", "title": "Maximum Twin Sum of a Linked List", "slug": "maximum-twin-sum-of-a-linked-list", "difficulty": "Medium", "problem_number": 2130},
    {"category": "Linked List", "title": "Sort List", "slug": "sort-list", "difficulty": "Medium", "problem_number": 148},
    {"category": "Linked List", "title": "Swap Nodes in Pairs", "slug": "swap-nodes-in-pairs", "difficulty": "Medium", "problem_number": 24},
    # ── Trees (extras) ───────────────────────────────────────────────────────────
    {"category": "Trees", "title": "Binary Tree Preorder Traversal", "slug": "binary-tree-preorder-traversal", "difficulty": "Easy", "problem_number": 144},
    {"category": "Trees", "title": "Binary Tree Inorder Traversal", "slug": "binary-tree-inorder-traversal", "difficulty": "Easy", "problem_number": 94},
    {"category": "Trees", "title": "Binary Tree Postorder Traversal", "slug": "binary-tree-postorder-traversal", "difficulty": "Easy", "problem_number": 145},
    {"category": "Trees", "title": "Minimum Absolute Difference in BST", "slug": "minimum-absolute-difference-in-bst", "difficulty": "Easy", "problem_number": 530},
    {"category": "Trees", "title": "Insert into a Binary Search Tree", "slug": "insert-into-a-binary-search-tree", "difficulty": "Medium", "problem_number": 701},
    {"category": "Trees", "title": "Delete Node in a BST", "slug": "delete-node-in-a-bst", "difficulty": "Medium", "problem_number": 450},
    {"category": "Trees", "title": "Binary Tree Zigzag Level Order Traversal", "slug": "binary-tree-zigzag-level-order-traversal", "difficulty": "Medium", "problem_number": 103},
    # ── Heap / Priority Queue (extras) ───────────────────────────────────────────
    {"category": "Heap / Priority Queue", "title": "Kth Largest Element in a Stream", "slug": "kth-largest-element-in-a-stream", "difficulty": "Easy", "problem_number": 703},
    {"category": "Heap / Priority Queue", "title": "Reorganize String", "slug": "reorganize-string", "difficulty": "Medium", "problem_number": 767},
    {"category": "Heap / Priority Queue", "title": "Longest Happy String", "slug": "longest-happy-string", "difficulty": "Medium", "problem_number": 1405},
    {"category": "Heap / Priority Queue", "title": "Car Pooling", "slug": "car-pooling", "difficulty": "Medium", "problem_number": 1094},
    # ── Backtracking (extras) ────────────────────────────────────────────────────
    {"category": "Backtracking", "title": "Combinations", "slug": "combinations", "difficulty": "Medium", "problem_number": 77},
    {"category": "Backtracking", "title": "Combination Sum III", "slug": "combination-sum-iii", "difficulty": "Medium", "problem_number": 216},
    # ── Graphs (extras) ──────────────────────────────────────────────────────────
    {"category": "Graphs", "title": "Island Perimeter", "slug": "island-perimeter", "difficulty": "Easy", "problem_number": 463},
    {"category": "Graphs", "title": "Shortest Bridge", "slug": "shortest-bridge", "difficulty": "Medium", "problem_number": 934},
    {"category": "Graphs", "title": "Reorder Routes to Make All Paths Lead to the City Zero", "slug": "reorder-routes-to-make-all-paths-lead-to-the-city-zero", "difficulty": "Medium", "problem_number": 1466},
    {"category": "Graphs", "title": "Snakes and Ladders", "slug": "snakes-and-ladders", "difficulty": "Medium", "problem_number": 909},
    {"category": "Graphs", "title": "Open the Lock", "slug": "open-the-lock", "difficulty": "Medium", "problem_number": 752},
    {"category": "Graphs", "title": "Find Eventual Safe States", "slug": "find-eventual-safe-states", "difficulty": "Medium", "problem_number": 802},
    # ── Advanced Graphs (extras) ─────────────────────────────────────────────────
    {"category": "Advanced Graphs", "title": "Path with Maximum Probability", "slug": "path-with-maximum-probability", "difficulty": "Medium", "problem_number": 1514},
    # ── 1-D DP (extras) ──────────────────────────────────────────────────────────
    {"category": "1-D DP", "title": "N-th Tribonacci Number", "slug": "n-th-tribonacci-number", "difficulty": "Easy", "problem_number": 1137},
    {"category": "1-D DP", "title": "Delete and Earn", "slug": "delete-and-earn", "difficulty": "Medium", "problem_number": 740},
    {"category": "1-D DP", "title": "Maximum Length of Pair Chain", "slug": "maximum-length-of-pair-chain", "difficulty": "Medium", "problem_number": 646},
    {"category": "1-D DP", "title": "Integer Break", "slug": "integer-break", "difficulty": "Medium", "problem_number": 343},
    # ── 2-D DP (extras) ──────────────────────────────────────────────────────────
    {"category": "2-D DP", "title": "Minimum Path Sum", "slug": "minimum-path-sum", "difficulty": "Medium", "problem_number": 64},
    {"category": "2-D DP", "title": "Unique Paths II", "slug": "unique-paths-ii", "difficulty": "Medium", "problem_number": 63},
    {"category": "2-D DP", "title": "Last Stone Weight II", "slug": "last-stone-weight-ii", "difficulty": "Medium", "problem_number": 1049},
    {"category": "2-D DP", "title": "Ones and Zeroes", "slug": "ones-and-zeroes", "difficulty": "Medium", "problem_number": 474},
    # ── Greedy (extras) ──────────────────────────────────────────────────────────
    {"category": "Greedy", "title": "Maximum Length of Pair Chain", "slug": "maximum-length-of-pair-chain", "difficulty": "Medium", "problem_number": 646},
    {"category": "Greedy", "title": "Minimum Number of Arrows to Burst Balloons", "slug": "minimum-number-of-arrows-to-burst-balloons", "difficulty": "Medium", "problem_number": 452},
    {"category": "Greedy", "title": "Two City Scheduling", "slug": "two-city-scheduling", "difficulty": "Medium", "problem_number": 1029},
    # ── Intervals (extras) ───────────────────────────────────────────────────────
    {"category": "Intervals", "title": "Minimum Number of Arrows to Burst Balloons", "slug": "minimum-number-of-arrows-to-burst-balloons", "difficulty": "Medium", "problem_number": 452},
    {"category": "Intervals", "title": "Remove Covered Intervals", "slug": "remove-covered-intervals", "difficulty": "Medium", "problem_number": 1288},
    # ── Math & Geometry (extras) ─────────────────────────────────────────────────
    {"category": "Math & Geometry", "title": "Roman to Integer", "slug": "roman-to-integer", "difficulty": "Easy", "problem_number": 13},
    {"category": "Math & Geometry", "title": "Palindrome Number", "slug": "palindrome-number", "difficulty": "Easy", "problem_number": 9},
    # ── Bit Manipulation (extras) ────────────────────────────────────────────────
    {"category": "Bit Manipulation", "title": "Add Binary", "slug": "add-binary", "difficulty": "Easy", "problem_number": 67},
    {"category": "Bit Manipulation", "title": "Find the Difference", "slug": "find-the-difference", "difficulty": "Easy", "problem_number": 389},
]

def _dedupe_by_slug(problems: list) -> list:
    """Remove duplicate slugs, keeping the first occurrence."""
    seen = set()
    result = []
    for p in problems:
        if p["slug"] not in seen:
            seen.add(p["slug"])
            result.append(p)
    return result

NEETCODE250_PROBLEMS = _dedupe_by_slug(NEETCODE150_PROBLEMS + NEETCODE250_EXTRAS)
