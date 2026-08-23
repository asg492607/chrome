"""
8-bit Compact Tag Enum and Node Flags for ECS Memory Subsystem.
Zero-overhead definitions designed to fit inside single byte fields in 32-byte DOM entities.
"""

from enum import IntEnum, IntFlag

class TagType(IntEnum):
    # Special / Structure
    UNKNOWN = 0
    DOCUMENT = 1
    HTML = 2
    HEAD = 3
    BODY = 4
    TEXT = 5
    COMMENT = 6

    # Block Elements
    DIV = 10
    P = 11
    H1 = 12
    H2 = 13
    H3 = 14
    H4 = 15
    H5 = 16
    H6 = 17
    SECTION = 18
    ARTICLE = 19
    NAV = 20
    HEADER = 21
    FOOTER = 22
    MAIN = 23
    BLOCKQUOTE = 24
    HR = 25
    UL = 26
    OL = 27
    LI = 28

    # Inline Elements
    SPAN = 40
    A = 41
    STRONG = 42
    EM = 43
    B = 44
    I = 45
    CODE = 46
    BR = 47

    # Form / Interactive Elements
    BUTTON = 60
    INPUT = 61
    FORM = 62
    LABEL = 63
    SELECT = 64
    OPTION = 65
    TEXTAREA = 66

    # Media / Embeds
    IMG = 80
    CANVAS = 81
    SVG = 82
    VIDEO = 83
    AUDIO = 84

    # Custom
    CUSTOM = 255


# Tag Name to TagType mapping table for high-speed string lookup
TAG_NAME_TO_TYPE = {
    "html": TagType.HTML,
    "head": TagType.HEAD,
    "body": TagType.BODY,
    "text": TagType.TEXT,
    "div": TagType.DIV,
    "p": TagType.P,
    "h1": TagType.H1,
    "h2": TagType.H2,
    "h3": TagType.H3,
    "h4": TagType.H4,
    "h5": TagType.H5,
    "h6": TagType.H6,
    "section": TagType.SECTION,
    "article": TagType.ARTICLE,
    "nav": TagType.NAV,
    "header": TagType.HEADER,
    "footer": TagType.FOOTER,
    "main": TagType.MAIN,
    "blockquote": TagType.BLOCKQUOTE,
    "hr": TagType.HR,
    "ul": TagType.UL,
    "ol": TagType.OL,
    "li": TagType.LI,
    "span": TagType.SPAN,
    "a": TagType.A,
    "strong": TagType.STRONG,
    "em": TagType.EM,
    "b": TagType.B,
    "i": TagType.I,
    "code": TagType.CODE,
    "br": TagType.BR,
    "button": TagType.BUTTON,
    "input": TagType.INPUT,
    "form": TagType.FORM,
    "label": TagType.LABEL,
    "select": TagType.SELECT,
    "option": TagType.OPTION,
    "textarea": TagType.TEXTAREA,
    "img": TagType.IMG,
    "canvas": TagType.CANVAS,
    "svg": TagType.SVG,
    "video": TagType.VIDEO,
    "audio": TagType.AUDIO,
}

TAG_TYPE_TO_NAME = {v: k for k, v in TAG_NAME_TO_TYPE.items()}


class NodeFlags(IntFlag):
    """8-bit bitmask flags representing entity state and dirty-propagation tracking."""
    NONE = 0
    VISIBILITY = 1 << 0       # Bit 0: Is element visible? (1=visible, 0=hidden)
    DIRTY_LAYOUT = 1 << 1     # Bit 1: Geometry needs recalculation
    DIRTY_STYLE = 1 << 2      # Bit 2: CSS cascade needs re-evaluation
    HOVER = 1 << 3            # Bit 3: Pointer is hovering over entity
    FOCUSED = 1 << 4          # Bit 4: Keyboard focus active
    ACTIVE = 1 << 5           # Bit 5: Mouse pressed / active state
    INLINE_DISPLAY = 1 << 6   # Bit 6: Inline display box vs Block
    TEXT_NODE = 1 << 7        # Bit 7: Is text node
