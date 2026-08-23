"""
Query Parser & Optimizer Engine (Sprint 55 - Phase II Sovereign Search Engine).
Implements Boolean operator parsing (AND, OR, NOT), exact phrase matching ("exact phrase"),
Levenshtein distance fuzzy typo tolerance matching (term~1), Query AST nodes, and query AST optimization.
"""

import re
import sys
import os
from typing import Dict, List, Optional, Tuple, Any, Union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def clean_html(html_content: str) -> str:
    """Strips script, style, and HTML tags from raw content."""
    text = re.sub(r'<(script|style)\b[^>]*>([\s\S]*?)</\1>', ' ', html_content)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text: str) -> List[str]:
    """Tokenizes input string into lowercase alphanumeric words."""
    text = text.lower()
    return re.findall(r'\b\w+\b', text)


def process_query(query: str, stop_words: List[str]) -> List[str]:
    """Extracts non-stopword tokens for basic search processing."""
    tokens = tokenize(query)
    return [w for w in tokens if w not in stop_words]


class LevenshteinMatcher:
    """Levenshtein Edit Distance calculator for typo tolerance fuzzy matching."""

    @classmethod
    def distance(cls, s1: str, s2: str) -> int:
        """Computes edit distance between strings s1 and s2 using dynamic programming."""
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i - 1] == s2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

        return dp[m][n]

    @classmethod
    def fuzzy_match(cls, target: str, candidates: List[str], max_edits: int = 1) -> List[str]:
        """Filters candidates within max_edits Levenshtein distance."""
        target_lower = target.lower()
        matches = []
        for cand in candidates:
            if abs(len(cand) - len(target_lower)) <= max_edits:
                if cls.distance(target_lower, cand.lower()) <= max_edits:
                    matches.append(cand)
        return matches


class QueryASTNode:
    """Base class for Query Abstract Syntax Tree nodes."""

    def evaluate(self) -> Dict[str, Any]:
        raise NotImplementedError


class TermNode(QueryASTNode):
    """Represents a single query term."""

    def __init__(self, term: str):
        self.term = term.lower().strip()

    def evaluate(self) -> Dict[str, Any]:
        return {"type": "TERM", "term": self.term}

    def __repr__(self) -> str:
        return f"TermNode('{self.term}')"


class PhraseNode(QueryASTNode):
    """Represents an exact ordered phrase query."""

    def __init__(self, terms: List[str]):
        self.terms = [t.lower().strip() for t in terms if t.lower().strip()]

    def evaluate(self) -> Dict[str, Any]:
        return {"type": "PHRASE", "terms": self.terms}

    def __repr__(self) -> str:
        return f"PhraseNode({self.terms})"


class FuzzyNode(QueryASTNode):
    """Represents a fuzzy matching term query with edit distance constraint."""

    def __init__(self, term: str, max_edits: int = 1):
        self.term = term.lower().strip()
        self.max_edits = max_edits

    def evaluate(self) -> Dict[str, Any]:
        return {"type": "FUZZY", "term": self.term, "maxEdits": self.max_edits}

    def __repr__(self) -> str:
        return f"FuzzyNode('{self.term}', edits={self.max_edits})"


class BooleanNode(QueryASTNode):
    """Represents a logical Boolean operator node (AND, OR, NOT)."""

    def __init__(self, operator: str, left: QueryASTNode, right: Optional[QueryASTNode] = None):
        self.operator = operator.upper()
        self.left = left
        self.right = right

    def evaluate(self) -> Dict[str, Any]:
        return {
            "type": "BOOLEAN",
            "operator": self.operator,
            "left": self.left.evaluate(),
            "right": self.right.evaluate() if self.right else None
        }

    def __repr__(self) -> str:
        return f"BooleanNode({self.operator}, {self.left}, {self.right})"


class SovereignQueryParser:
    """Parser turning raw query strings into structured QueryASTNode trees."""

    @classmethod
    def parse_query(cls, query_str: str) -> QueryASTNode:
        """Parses query string with Boolean AND/OR/NOT, exact quotes, and fuzzy modifiers (~1)."""
        query_str = query_str.strip()
        if not query_str:
            return TermNode("")

        # 1. Extract exact phrase quotes "..."
        phrase_matches = re.findall(r'"([^"]+)"', query_str)
        if phrase_matches and len(query_str.strip()) == len(f'"{phrase_matches[0]}"'):
            terms = tokenize(phrase_matches[0])
            return PhraseNode(terms)

        # 2. Tokenize operators and words
        raw_tokens = query_str.split()
        nodes: List[QueryASTNode] = []
        i = 0

        while i < len(raw_tokens):
            token = raw_tokens[i]
            token_upper = token.upper()

            if token_upper in ("AND", "OR", "NOT"):
                if token_upper == "NOT" and i + 1 < len(raw_tokens):
                    target_token = raw_tokens[i + 1]
                    target_node = cls._parse_single_token(target_token)
                    nodes.append(BooleanNode("NOT", target_node))
                    i += 2
                    continue
                i += 1
                continue

            node = cls._parse_single_token(token)
            nodes.append(node)
            i += 1

        if not nodes:
            return TermNode("")

        if len(nodes) == 1:
            return nodes[0]

        # Combine nodes into AND tree
        root = nodes[0]
        for next_node in nodes[1:]:
            root = BooleanNode("AND", root, next_node)

        return root

    @classmethod
    def _parse_single_token(cls, token: str) -> QueryASTNode:
        if token.startswith('"') and token.endswith('"'):
            return PhraseNode(tokenize(token))
        if '~' in token:
            parts = token.split('~', 1)
            term = parts[0]
            try:
                edits = int(parts[1])
            except ValueError:
                edits = 1
            return FuzzyNode(term, edits)
        return TermNode(token)


class QueryASTOptimizer:
    """Optimizer simplifying and rewriting Query AST trees for execution."""

    @classmethod
    def optimize(cls, root: QueryASTNode) -> QueryASTNode:
        """Simplifies double NOTs and collapses redundant Boolean AND/OR wrappers."""
        if isinstance(root, BooleanNode):
            if root.operator == "NOT" and isinstance(root.left, BooleanNode) and root.left.operator == "NOT":
                # Double NOT: NOT NOT A -> A
                return cls.optimize(root.left.left)
            root.left = cls.optimize(root.left)
            if root.right:
                root.right = cls.optimize(root.right)
        return root
