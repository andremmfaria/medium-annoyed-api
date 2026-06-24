from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from medium_annoyed_api.frontmatter import read_article
from medium_annoyed_api.markdown_medium import article_to_medium_paragraphs


class ConversionTests(unittest.TestCase):
    def test_frontmatter_multiline_tags(self) -> None:
        with TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text(
                """---
title: Test
tags:
  - python
  - agents
---

Body.
""",
                encoding="utf-8",
            )

            parsed = read_article(article)

        self.assertEqual(parsed.title, "Test")
        self.assertEqual(parsed.tags, ["python", "agents"])

    def test_markdown_conversion_handles_common_blocks(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image = tmp_path / "screen.png"
            image.write_bytes(b"not really png")
            markdown = """Intro with [a link](https://example.com) and **bold**.

| Name | Value |
| --- | --- |
| A | 1 |

![Screen](screen.png)

```python
print("hello")
```
"""

            paragraphs = article_to_medium_paragraphs("Title", markdown, tmp_path)
            texts = [paragraph.get("text") for paragraph in paragraphs]

        self.assertEqual(paragraphs[0]["type"], 3)
        self.assertIn("Name | Value", texts)
        self.assertTrue(any(paragraph["type"] == 4 and paragraph["source"] == str(image) for paragraph in paragraphs))
        self.assertTrue(any(paragraph["type"] == 8 and 'print("hello")' in paragraph["text"] for paragraph in paragraphs))
        self.assertTrue(any(markup["type"] == 3 for paragraph in paragraphs for markup in paragraph.get("markups", [])))


if __name__ == "__main__":
    unittest.main()
