"""
Inverted Index & Positional Indexing Engine (Sprint 53 - Phase II Sovereign Search Engine).
Implements inverted document posting lists, positional offset tracking, Variable-Byte (Varint) delta gap integer compression,
phrase query proximity matching, and multi-shard partition distribution.
"""

import json
import os
import sys
import zlib
from typing import Dict, List, Optional, Set, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from search_platform.search_config import SearchConfig
from search_platform.query_processor import tokenize
from search_platform.tfidf_engine import TFIDFEngine


class Posting:
    """Represents a document posting entry containing document ID, term frequency, and positional offsets."""

    def __init__(self, doc_id: str, term_frequency: int, positions: Optional[List[int]] = None):
        self.doc_id = doc_id
        self.term_frequency = term_frequency
        self.positions = positions or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "docId": self.doc_id,
            "tf": self.term_frequency,
            "positions": self.positions
        }

    def __repr__(self) -> str:
        return f"Posting(doc='{self.doc_id}', tf={self.term_frequency}, pos={self.positions})"


class VarintCompressor:
    """Variable-Byte (Varint) integer encoder and delta gap compressor."""

    @classmethod
    def encode_varint(cls, number: int) -> bytes:
        """Encodes a single unsigned integer using Variable-Byte (7 bits per byte)."""
        buf = bytearray()
        while True:
            towrite = number & 0x7f
            number >>= 7
            if number != 0:
                buf.append(towrite | 0x80)
            else:
                buf.append(towrite)
                break
        return bytes(buf)

    @classmethod
    def decode_varint(cls, stream: bytes, offset: int = 0) -> Tuple[int, int]:
        """Decodes a single varint from byte stream starting at offset. Returns (value, bytes_read)."""
        res = 0
        shift = 0
        read = 0
        while offset < len(stream):
            b = stream[offset]
            offset += 1
            read += 1
            res |= (b & 0x7f) << shift
            if (b & 0x80) == 0:
                break
            shift += 7
        return res, read

    @classmethod
    def delta_encode(cls, numbers: List[int]) -> bytes:
        """Encodes a sorted list of integer offsets using delta gap encoding."""
        if not numbers:
            return b""
        buf = bytearray()
        last = 0
        for num in numbers:
            delta = num - last
            buf.extend(cls.encode_varint(delta))
            last = num
        return bytes(buf)

    @classmethod
    def delta_decode(cls, encoded_bytes: bytes) -> List[int]:
        """Decodes delta-encoded varint bytes back to original sorted integer list."""
        numbers = []
        offset = 0
        last = 0
        while offset < len(encoded_bytes):
            delta, read = cls.decode_varint(encoded_bytes, offset)
            offset += read
            last += delta
            numbers.append(last)
        return numbers


class InvertedPositionalIndex:
    """Inverted Positional Index dictionary holding document posting lists."""

    def __init__(self):
        self._dictionary: Dict[str, List[Posting]] = {}
        self._documents: Dict[str, Dict[str, Any]] = {}

    def add_document(self, doc_id: str, title: str, clean_text: str) -> None:
        """Indexes a document into inverted posting lists with positional offsets."""
        snippet = clean_text[:SearchConfig.SNIPPET_LENGTH] + "..." if len(clean_text) > SearchConfig.SNIPPET_LENGTH else clean_text
        self._documents[doc_id] = {
            "title": title,
            "snippet": snippet,
            "wordCount": len(clean_text.split())
        }

        tokens = tokenize(clean_text)
        term_positions: Dict[str, List[int]] = {}

        for pos, token in enumerate(tokens):
            if token in SearchConfig.STOP_WORDS:
                continue
            if token not in term_positions:
                term_positions[token] = []
            term_positions[token].append(pos)

        for term, positions in term_positions.items():
            if term not in self._dictionary:
                self._dictionary[term] = []
            posting = Posting(doc_id, len(positions), positions)
            self._dictionary[term].append(posting)

    def lookup_term(self, term: str) -> List[Posting]:
        """Queries posting list for specified term."""
        term_clean = term.lower().strip()
        return self._dictionary.get(term_clean, [])

    def lookup_phrase(self, phrase_terms: List[str]) -> List[str]:
        """Queries documents containing consecutive phrase terms."""
        if not phrase_terms:
            return []
        cleaned_terms = [t.lower().strip() for t in phrase_terms if t.lower().strip() not in SearchConfig.STOP_WORDS]
        if not cleaned_terms:
            return []

        first_term_postings = self.lookup_term(cleaned_terms[0])
        matching_docs = []

        for p in first_term_postings:
            doc_id = p.doc_id
            pos_list = p.positions

            for start_pos in pos_list:
                match_found = True
                for idx in range(1, len(cleaned_terms)):
                    target_term = cleaned_terms[idx]
                    target_postings = self.lookup_term(target_term)
                    target_doc_p = next((tp for tp in target_postings if tp.doc_id == doc_id), None)
                    if not target_doc_p or (start_pos + idx) not in target_doc_p.positions:
                        match_found = False
                        break
                if match_found:
                    matching_docs.append(doc_id)
                    break

        return matching_docs

    def get_terms_count(self) -> int:
        return len(self._dictionary)

    def get_docs_count(self) -> int:
        return len(self._documents)


class IndexShard:
    """Hash-partitioned multi-shard index partition manager."""

    def __init__(self, num_shards: int = 4):
        self.num_shards = num_shards
        self.shards: List[InvertedPositionalIndex] = [InvertedPositionalIndex() for _ in range(num_shards)]

    def get_shard_index(self, term: str) -> int:
        return zlib.adler32(term.encode('utf-8')) % self.num_shards

    def add_document(self, doc_id: str, title: str, clean_text: str) -> None:
        for shard in self.shards:
            shard.add_document(doc_id, title, clean_text)

    def lookup_term(self, term: str) -> List[Posting]:
        shard_idx = self.get_shard_index(term)
        return self.shards[shard_idx].lookup_term(term)


class IndexBuilder:
    """Backward-compatible index builder for search engine pipeline."""

    def __init__(self, index_file: str = SearchConfig.INDEX_FILE):
        self.index_file = index_file
        self.positional_index = InvertedPositionalIndex()
        self.index: Dict[str, Dict[str, float]] = {}
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.tfidf_engine = TFIDFEngine()

    def build_index(self, crawled_pages: List[Any]) -> None:
        self.positional_index = InvertedPositionalIndex()
        self.index = {}
        self.documents = {}

        num_docs = len(crawled_pages)
        if num_docs == 0:
            return

        doc_term_counts: Dict[str, Dict[str, int]] = {}
        doc_total_words: Dict[str, int] = {}

        for page in crawled_pages:
            url = page.url
            text = page.text
            title = page.title

            self.positional_index.add_document(url, title, text)
            snippet = text[:SearchConfig.SNIPPET_LENGTH] + "..." if len(text) > SearchConfig.SNIPPET_LENGTH else text
            self.documents[url] = {
                "title": title,
                "snippet": snippet
            }

            tokens = tokenize(text)
            tokens = [w for w in tokens if w not in SearchConfig.STOP_WORDS]
            doc_total_words[url] = len(tokens)

            counts: Dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            doc_term_counts[url] = counts

        self.index = self.tfidf_engine.compute(num_docs, doc_term_counts, doc_total_words)
        self.save_index()

    def save_index(self) -> None:
        data = {
            "documents": self.documents,
            "index": self.index
        }
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def load_index(self) -> bool:
        if not os.path.exists(self.index_file):
            return False
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.documents = data.get("documents", {})
            self.index = data.get("index", {})
            return True
        except Exception:
            return False
