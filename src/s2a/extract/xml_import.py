from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from s2a.normalize.models import WordPressExport, WordPressItem


NAMESPACES = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "wp": "http://wordpress.org/export/1.2/",
}


def import_wordpress_xml(xml_path: Path) -> WordPressExport:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    channel = root.find("channel")

    if channel is None:
        raise ValueError(f"No <channel> element found in {xml_path}")

    site_title = text_at(channel.find("title"))
    site_link = text_at(channel.find("link"))
    site_description = text_at(channel.find("description"))
    items: list[WordPressItem] = []

    for item in channel.findall("item"):
        link = text_at(item.find("link"))
        post_type = text_at(item.find("wp:post_type", NAMESPACES))
        status = text_at(item.find("wp:status", NAMESPACES))
        slug = text_at(item.find("wp:post_name", NAMESPACES)) or slug_from_link(link)

        categories: list[str] = []
        tags: list[str] = []
        for category in item.findall("category"):
            name = (category.text or "").strip()
            domain = category.attrib.get("domain", "")
            if not name:
                continue
            if domain == "category":
                categories.append(name)
            elif domain == "post_tag":
                tags.append(name)

        items.append(
            WordPressItem(
                title=text_at(item.find("title")),
                link=link,
                post_type=post_type,
                status=status,
                slug=slug,
                guid=text_at(item.find("guid")),
                published_at=(
                    text_at(item.find("wp:post_date_gmt", NAMESPACES))
                    or text_at(item.find("wp:post_date", NAMESPACES))
                    or text_at(item.find("pubDate"))
                ),
                excerpt_html=text_at(item.find("excerpt:encoded", NAMESPACES)),
                content_html=text_at(item.find("content:encoded", NAMESPACES)),
                categories=list(dict.fromkeys(categories)),
                tags=list(dict.fromkeys(tags)),
            )
        )

    warnings: list[str] = []
    if not any(item.post_type == "post" for item in items):
        warnings.append("No WordPress 'post' items were found in the XML export.")

    return WordPressExport(
        source_path=str(xml_path),
        site_title=site_title,
        site_link=site_link,
        site_description=site_description,
        items=items,
        warnings=warnings,
    )


def text_at(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    text = element.text.strip()
    return text or None


def slug_from_link(link: str | None) -> str | None:
    if not link:
        return None
    path = urlsplit(link).path.strip("/")
    if not path:
        return None
    return path.split("/")[-1]
