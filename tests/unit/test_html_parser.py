from src.tools.html_parser import HtmlParser


class TestHtmlParser:
    def test_extract_text(self):
        html = "<html><body><h1>Title</h1><p>Content</p></body></html>"
        parser = HtmlParser()
        text = parser.extract_text(html)
        assert "Title" in text
        assert "Content" in text

    def test_extract_links(self):
        html = '<html><body><a href="https://a.com">A</a><a href="https://b.com">B</a></body></html>'
        parser = HtmlParser()
        links = parser.extract_links(html, base_url="https://example.com")
        assert len(links) == 2
        assert links[0]["url"] == "https://a.com"

    def test_extract_meta(self):
        html = '<html><head><meta name="description" content="test desc"></head></html>'
        parser = HtmlParser()
        meta = parser.extract_meta(html)
        assert meta.get("description") == "test desc"

    def test_empty_html(self):
        parser = HtmlParser()
        assert parser.extract_text("") == ""
        assert parser.extract_links("") == []
