from browser_engine.parsing.html_parser import HTMLParser

class DOMBuilder:
    def __init__(self):
        self.parser = HTMLParser()

    def build(self, html_text):
        """
        Wrapper to conceptually separate DOM construction from HTML parsing.
        """
        return self.parser.parse(html_text)
