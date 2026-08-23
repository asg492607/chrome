class CrawledPage:
    def __init__(self, url, title, text, raw_html):
        self.url = url
        self.title = title
        self.text = text
        self.raw_html = raw_html

class SearchResult:
    def __init__(self, url, title, snippet, score):
        self.url = url
        self.title = title
        self.snippet = snippet
        self.score = score

    def to_dict(self):
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "score": self.score
        }

