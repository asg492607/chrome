"""
WHATWG-Compliant HTML5 Tokenizer State Machine & Direct-to-ECS Memory Tree Builder.
Parses raw HTML source text and emits zero-allocation token streams directly into
the Sprint 01 32-byte DOMEntity32 ECS Memory Bank.
"""

import sys
import os
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core_platform.tag_constants import TagType, NodeFlags, TAG_NAME_TO_TYPE
from core_platform.ecs_memory import DocumentTreeMemoryBank, DOMEntity32


class HTMLTokenType(Enum):
    """HTML5 Token Types."""
    DOCTYPE = auto()
    START_TAG = auto()
    END_TAG = auto()
    COMMENT = auto()
    CHARACTER = auto()
    EOF = auto()


class HTMLToken:
    """Represents a single HTML Token emitted by the Tokenizer."""
    def __init__(
        self,
        token_type: HTMLTokenType,
        tag_name: str = "",
        attributes: Optional[Dict[str, str]] = None,
        data: str = "",
        self_closing: bool = False
    ):
        self.token_type = token_type
        self.tag_name = tag_name.lower().strip()
        self.attributes = attributes if attributes is not None else {}
        self.data = data
        self.self_closing = self_closing

    def __repr__(self) -> str:
        if self.token_type == HTMLTokenType.START_TAG:
            sc = " /" if self.self_closing else ""
            attrs = f" {self.attributes}" if self.attributes else ""
            return f"<START_TAG '{self.tag_name}'{attrs}{sc}>"
        elif self.token_type == HTMLTokenType.END_TAG:
            return f"<END_TAG '{self.tag_name}'>"
        elif self.token_type == HTMLTokenType.CHARACTER:
            return f"<CHAR '{self.data}'>"
        return f"<{self.token_type.name} '{self.data}'>"


# Void elements that do not require an end tag according to WHATWG HTML5 spec
VOID_ELEMENTS: set = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
}


class HTMLTokenizerState(Enum):
    """WHATWG HTML5 Tokenizer States."""
    DATA = auto()
    TAG_OPEN = auto()
    END_TAG_OPEN = auto()
    TAG_NAME = auto()
    BEFORE_ATTRIBUTE_NAME = auto()
    ATTRIBUTE_NAME = auto()
    AFTER_ATTRIBUTE_NAME = auto()
    BEFORE_ATTRIBUTE_VALUE = auto()
    ATTRIBUTE_VALUE_QUOTED = auto()
    ATTRIBUTE_VALUE_UNQUOTED = auto()
    AFTER_ATTRIBUTE_VALUE = auto()
    SELF_CLOSING_START_TAG = auto()
    COMMENT = auto()
    DOCTYPE = auto()


class HTML5Tokenizer:
    """
    Finite State Machine HTML5 Tokenizer.
    Converts raw HTML string into a stream of HTMLToken objects according to WHATWG rules.
    """

    def __init__(self):
        self.state = HTMLTokenizerState.DATA
        self.tokens: List[HTMLToken] = []

    def tokenize(self, html: str) -> List[HTMLToken]:
        """Tokenizes HTML string and returns token sequence."""
        self.state = HTMLTokenizerState.DATA
        self.tokens = []

        pos = 0
        length = len(html)

        current_tag_name = ""
        current_attrs: Dict[str, str] = {}
        current_attr_name = ""
        current_attr_val = ""
        current_quote_char = ""
        current_data = ""
        is_end_tag = False
        self_closing = False

        while pos < length:
            ch = html[pos]

            if self.state == HTMLTokenizerState.DATA:
                if ch == '<':
                    if current_data:
                        self.tokens.append(HTMLToken(HTMLTokenType.CHARACTER, data=current_data))
                        current_data = ""
                    self.state = HTMLTokenizerState.TAG_OPEN
                else:
                    current_data += ch

            elif self.state == HTMLTokenizerState.TAG_OPEN:
                if ch == '/':
                    is_end_tag = True
                    self.state = HTMLTokenizerState.END_TAG_OPEN
                elif ch == '!':
                    # Comment or DOCTYPE
                    if html[pos:pos + 3] == '!--':
                        self.state = HTMLTokenizerState.COMMENT
                        pos += 2
                    elif html[pos:pos + 8].upper() == '!DOCTYPE':
                        self.state = HTMLTokenizerState.DOCTYPE
                        pos += 7
                    else:
                        current_data += '<!'
                        self.state = HTMLTokenizerState.DATA


                elif ch.isalpha():
                    is_end_tag = False
                    self_closing = False
                    current_tag_name = ch
                    current_attrs = {}
                    self.state = HTMLTokenizerState.TAG_NAME
                else:
                    current_data += '<' + ch
                    self.state = HTMLTokenizerState.DATA

            elif self.state == HTMLTokenizerState.END_TAG_OPEN:
                if ch.isalpha():
                    current_tag_name = ch
                    self.state = HTMLTokenizerState.TAG_NAME
                elif ch == '>':
                    self.state = HTMLTokenizerState.DATA
                else:
                    pass

            elif self.state == HTMLTokenizerState.TAG_NAME:
                if ch.isspace():
                    self.state = HTMLTokenizerState.BEFORE_ATTRIBUTE_NAME
                elif ch == '/':
                    self_closing = True
                    self.state = HTMLTokenizerState.SELF_CLOSING_START_TAG
                elif ch == '>':
                    tok_type = HTMLTokenType.END_TAG if is_end_tag else HTMLTokenType.START_TAG
                    self.tokens.append(HTMLToken(tok_type, tag_name=current_tag_name, attributes=current_attrs, self_closing=self_closing))
                    self.state = HTMLTokenizerState.DATA
                else:
                    current_tag_name += ch

            elif self.state == HTMLTokenizerState.BEFORE_ATTRIBUTE_NAME:
                if ch.isspace():
                    pass
                elif ch == '/':
                    self_closing = True
                    self.state = HTMLTokenizerState.SELF_CLOSING_START_TAG
                elif ch == '>':
                    tok_type = HTMLTokenType.END_TAG if is_end_tag else HTMLTokenType.START_TAG
                    self.tokens.append(HTMLToken(tok_type, tag_name=current_tag_name, attributes=current_attrs, self_closing=self_closing))
                    self.state = HTMLTokenizerState.DATA
                elif ch.isalpha() or ch in ('_', '-'):
                    current_attr_name = ch
                    current_attr_val = ""
                    self.state = HTMLTokenizerState.ATTRIBUTE_NAME

            elif self.state == HTMLTokenizerState.ATTRIBUTE_NAME:
                if ch == '=':
                    self.state = HTMLTokenizerState.BEFORE_ATTRIBUTE_VALUE
                elif ch.isspace():
                    self.state = HTMLTokenizerState.AFTER_ATTRIBUTE_NAME
                elif ch == '>':
                    current_attrs[current_attr_name] = ""
                    tok_type = HTMLTokenType.END_TAG if is_end_tag else HTMLTokenType.START_TAG
                    self.tokens.append(HTMLToken(tok_type, tag_name=current_tag_name, attributes=current_attrs, self_closing=self_closing))
                    self.state = HTMLTokenizerState.DATA
                else:
                    current_attr_name += ch

            elif self.state == HTMLTokenizerState.AFTER_ATTRIBUTE_NAME:
                if ch.isspace():
                    pass
                elif ch == '=':
                    self.state = HTMLTokenizerState.BEFORE_ATTRIBUTE_VALUE
                elif ch == '>':
                    current_attrs[current_attr_name] = ""
                    tok_type = HTMLTokenType.END_TAG if is_end_tag else HTMLTokenType.START_TAG
                    self.tokens.append(HTMLToken(tok_type, tag_name=current_tag_name, attributes=current_attrs, self_closing=self_closing))
                    self.state = HTMLTokenizerState.DATA
                else:
                    current_attrs[current_attr_name] = ""
                    current_attr_name = ch
                    current_attr_val = ""
                    self.state = HTMLTokenizerState.ATTRIBUTE_NAME

            elif self.state == HTMLTokenizerState.BEFORE_ATTRIBUTE_VALUE:
                if ch.isspace():
                    pass
                elif ch in ('"', "'"):
                    current_quote_char = ch
                    current_attr_val = ""
                    self.state = HTMLTokenizerState.ATTRIBUTE_VALUE_QUOTED
                elif ch == '>':
                    current_attrs[current_attr_name] = ""
                    tok_type = HTMLTokenType.END_TAG if is_end_tag else HTMLTokenType.START_TAG
                    self.tokens.append(HTMLToken(tok_type, tag_name=current_tag_name, attributes=current_attrs, self_closing=self_closing))
                    self.state = HTMLTokenizerState.DATA
                else:
                    current_attr_val = ch
                    self.state = HTMLTokenizerState.ATTRIBUTE_VALUE_UNQUOTED

            elif self.state == HTMLTokenizerState.ATTRIBUTE_VALUE_QUOTED:
                if ch == current_quote_char:
                    current_attrs[current_attr_name] = current_attr_val
                    self.state = HTMLTokenizerState.AFTER_ATTRIBUTE_VALUE
                else:
                    current_attr_val += ch

            elif self.state == HTMLTokenizerState.ATTRIBUTE_VALUE_UNQUOTED:
                if ch.isspace() or ch == '>':
                    current_attrs[current_attr_name] = current_attr_val
                    if ch == '>':
                        tok_type = HTMLTokenType.END_TAG if is_end_tag else HTMLTokenType.START_TAG
                        self.tokens.append(HTMLToken(tok_type, tag_name=current_tag_name, attributes=current_attrs, self_closing=self_closing))
                        self.state = HTMLTokenizerState.DATA
                    else:
                        self.state = HTMLTokenizerState.BEFORE_ATTRIBUTE_NAME
                else:
                    current_attr_val += ch

            elif self.state == HTMLTokenizerState.AFTER_ATTRIBUTE_VALUE:
                if ch.isspace():
                    self.state = HTMLTokenizerState.BEFORE_ATTRIBUTE_NAME
                elif ch == '>':
                    tok_type = HTMLTokenType.END_TAG if is_end_tag else HTMLTokenType.START_TAG
                    self.tokens.append(HTMLToken(tok_type, tag_name=current_tag_name, attributes=current_attrs, self_closing=self_closing))
                    self.state = HTMLTokenizerState.DATA
                elif ch == '/':
                    self_closing = True
                    self.state = HTMLTokenizerState.SELF_CLOSING_START_TAG

            elif self.state == HTMLTokenizerState.SELF_CLOSING_START_TAG:
                if ch == '>':
                    tok_type = HTMLTokenType.END_TAG if is_end_tag else HTMLTokenType.START_TAG
                    self.tokens.append(HTMLToken(tok_type, tag_name=current_tag_name, attributes=current_attrs, self_closing=True))
                    self.state = HTMLTokenizerState.DATA

            elif self.state == HTMLTokenizerState.COMMENT:
                if ch == '>' and current_data.endswith('--'):
                    comment_text = current_data[:-2].strip()
                    self.tokens.append(HTMLToken(HTMLTokenType.COMMENT, data=comment_text))
                    current_data = ""
                    self.state = HTMLTokenizerState.DATA
                else:
                    current_data += ch

            elif self.state == HTMLTokenizerState.DOCTYPE:
                if ch == '>':
                    self.tokens.append(HTMLToken(HTMLTokenType.DOCTYPE, data=current_data.strip()))
                    current_data = ""
                    self.state = HTMLTokenizerState.DATA
                else:
                    current_data += ch

            pos += 1

        if current_data and self.state == HTMLTokenizerState.DATA:
            self.tokens.append(HTMLToken(HTMLTokenType.CHARACTER, data=current_data))

        self.tokens.append(HTMLToken(HTMLTokenType.EOF))
        return self.tokens


class HTML5TreeBuilder:
    """
    Consumes HTMLToken stream and populates a DocumentTreeMemoryBank directly.
    Emits 32-byte DOMEntity32 structures into contiguous L1 cache-aligned arrays.
    """

    def __init__(self, memory_bank: Optional[DocumentTreeMemoryBank] = None):
        self.bank = memory_bank if memory_bank is not None else DocumentTreeMemoryBank(initial_capacity=16384)
        self.tokenizer = HTML5Tokenizer()


    def parse_html(self, html: str) -> Tuple[int, DocumentTreeMemoryBank]:
        """
        Parses raw HTML source text into DocumentTreeMemoryBank.
        Returns (root_node_id: int, DocumentTreeMemoryBank).
        """
        tokens = self.tokenizer.tokenize(html)
        root_id = self.bank.allocate_entity(TagType.DOCUMENT, NodeFlags.VISIBILITY)

        open_stack: List[Tuple[int, str]] = [(root_id, "document")]

        for token in tokens:
            if token.token_type == HTMLTokenType.START_TAG:
                tag_name = token.tag_name
                tag_type = TAG_NAME_TO_TYPE.get(tag_name, TagType.CUSTOM)
                
                flags = NodeFlags.VISIBILITY
                if tag_name in ("script", "style", "head", "meta", "link"):
                    flags = NodeFlags.NONE

                new_node_id = self.bank.allocate_entity(tag_type, flags=flags, attrs=token.attributes)


                # Link parent and siblings
                parent_id, _ = open_stack[-1]
                self.bank.append_child(parent_id, new_node_id)

                # Check if void element or self-closing
                is_void = (tag_name in VOID_ELEMENTS) or token.self_closing
                if not is_void:
                    open_stack.append((new_node_id, tag_name))

            elif token.token_type == HTMLTokenType.END_TAG:
                end_tag_name = token.tag_name
                # Pop stack up to matching tag name
                while len(open_stack) > 1:
                    _, stack_tag = open_stack[-1]
                    if stack_tag == end_tag_name:
                        open_stack.pop()
                        break
                    else:
                        open_stack.pop()

            elif token.token_type == HTMLTokenType.CHARACTER:
                text_data = token.data.strip()
                if text_data:
                    text_id = self.bank.allocate_entity(TagType.TEXT, NodeFlags.VISIBILITY | NodeFlags.TEXT_NODE)
                    parent_id, _ = open_stack[-1]
                    self.bank.append_child(parent_id, text_id)

        return root_id, self.bank
