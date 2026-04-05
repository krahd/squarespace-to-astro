from pathlib import Path

from s2a.extract.xml_import import import_wordpress_xml


def test_import_wordpress_xml_extracts_posts_pages_and_taxonomy(tmp_path: Path) -> None:
    xml_path = tmp_path / "export.xml"
    xml_path.write_text(
        """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"
  xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:wp="http://wordpress.org/export/1.2/">
  <channel>
    <title>Example Site</title>
    <link>https://example.com</link>
    <description>Imported description</description>
    <item>
      <title>Welcome</title>
      <link>https://example.com/</link>
      <content:encoded><![CDATA[<p>Hello world</p>]]></content:encoded>
      <excerpt:encoded><![CDATA[<p>Short intro</p>]]></excerpt:encoded>
      <wp:post_type>page</wp:post_type>
      <wp:status>publish</wp:status>
      <wp:post_name>home</wp:post_name>
    </item>
    <item>
      <title>First Post</title>
      <link>https://example.com/blog/2026/04/05/first-post</link>
      <content:encoded><![CDATA[<p>Post body</p>]]></content:encoded>
      <excerpt:encoded><![CDATA[<p>Post excerpt</p>]]></excerpt:encoded>
      <wp:post_type>post</wp:post_type>
      <wp:status>publish</wp:status>
      <wp:post_name>first-post</wp:post_name>
      <category domain="category"><![CDATA[Updates]]></category>
      <category domain="post_tag"><![CDATA[launch]]></category>
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    imported = import_wordpress_xml(xml_path)

    assert imported.site_title == "Example Site"
    assert imported.site_description == "Imported description"
    assert len(imported.items) == 2
    assert imported.items[1].post_type == "post"
    assert imported.items[1].categories == ["Updates"]
    assert imported.items[1].tags == ["launch"]
