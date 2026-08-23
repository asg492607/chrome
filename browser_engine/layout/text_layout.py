import tkinter.font as tkfont

class HeadlessFont:
    def __init__(self, family="Arial", size=14, weight="normal", slant="roman"):
        self.family = family
        self.size = abs(size)
        self.weight = weight
        self.slant = slant

    def measure(self, text):
        multiplier = 0.62 if self.weight == "bold" else 0.54
        return max(4, int(len(text) * self.size * multiplier))

    def actual(self, option=None):
        props = {
            "family": self.family,
            "size": -self.size,
            "weight": self.weight,
            "slant": self.slant,
            "underline": 0,
            "overstrike": 0
        }
        if option:
            return props.get(option)
        return props

    def metrics(self, option=None):
        m = {
            "ascent": int(self.size * 0.8),
            "descent": int(self.size * 0.2),
            "linespace": int(self.size * 1.2),
            "fixed": 0
        }
        if option:
            return m.get(option)
        return m

class TextLayout:
    def __init__(self):
        self.font_cache = {}

    def get_font(self, style):
        family = style.get("font-family", "Arial")
        if family.lower() in ["sans-serif", "arial", "helvetica"]:
            family = "Arial"
        elif family.lower() in ["serif", "times", "times new roman"]:
            family = "Times"
        elif family.lower() in ["monospace", "courier", "courier new", "jetbrains mono"]:
            family = "Courier"
            
        size = style.get("font-size", "14px")
        try:
            size_px = int(size.replace("px", "").replace("pt", ""))
            size_tk = -size_px
        except:
            size_tk = -14

        weight = "bold" if style.get("font-weight") == "bold" else "normal"
        slant = "italic" if style.get("font-style") == "italic" else "roman"
        
        key = (family, size_tk, weight, slant)
        try:
            if key not in self.font_cache:
                self.font_cache[key] = tkfont.Font(family=family, size=size_tk, weight=weight, slant=slant)
            return self.font_cache[key]
        except Exception:
            return HeadlessFont(family=family, size=abs(size_tk), weight=weight, slant=slant)

    def measure_word(self, font, word):
        # 1.15x scale + padding to match canvas text spacing
        return int(font.measure(word) * 1.15) + 3

    def measure_space(self, font):
        return font.measure(" ") + 4

    def sanitize_text(self, text):
        text = " ".join(text.replace("\n", " ").split())
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
        return text
