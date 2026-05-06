from __future__ import annotations

from s2a.normalize.models import CrawlReport, CrawlSnapshot, PageReportEntry


def build_report(snapshot: CrawlSnapshot) -> CrawlReport:
    ok_pages = 0
    pages_with_json = 0
    password_gated_pages = 0
    unique_assets: set[str] = set()
    unique_internal_links: set[str] = set()
    warnings = list(snapshot.probe.warnings) + list(snapshot.warnings)
    page_entries: list[PageReportEntry] = []
    manual_follow_up: list[str] = []

    for page in snapshot.pages:
        if page.status_code and 200 <= page.status_code < 300:
            ok_pages += 1

        if page.json_probe and page.json_probe.available:
            pages_with_json += 1

        if page.password_gate_detected:
            password_gated_pages += 1

        unique_assets.update(page.asset_urls)
        unique_internal_links.update(page.internal_links)
        warnings.extend(page.warnings)

        page_entries.append(
            PageReportEntry(
                url=page.final_url or page.requested_url,
                status_code=page.status_code,
                title=page.title,
                json_available=bool(page.json_probe and page.json_probe.available),
                password_gate_detected=page.password_gate_detected,
            )
        )

    if not snapshot.probe.probably_squarespace:
        manual_follow_up.append(
            "Squarespace indicators were weak or missing; verify the target is a Squarespace site before trusting the crawl output."
        )

    if snapshot.probe.sitemap_status_code != 200:
        manual_follow_up.append(
            "No sitemap was retrieved successfully, so crawl coverage may be incomplete. "
            "If the site has RSS feeds, they will be used as supplementary seeds automatically."
        )
    elif len(snapshot.probe.sitemap_entries) == 0:
        rss_hint = (
            f" {len(snapshot.probe.rss_feeds)} RSS feed(s) were found and used as supplementary seeds."
            if snapshot.probe.rss_feeds
            else " No RSS feeds were found to supplement coverage."
        )
        manual_follow_up.append(
            "Sitemap was retrieved but contained no URL entries, so crawl coverage "
            "may be incomplete." + rss_hint
        )

    if pages_with_json == 0:
        manual_follow_up.append(
            "No Squarespace JSON endpoints were detected; later migration stages will rely mostly on rendered HTML fallbacks."
        )

    if password_gated_pages > 0 or snapshot.probe.password_gate_detected:
        manual_follow_up.append(
            "Password-gated pages were detected. Use auth-browser or crawl/migrate with --site-password or --storage-state to capture authenticated content before generating the final site."
        )

    if snapshot.probe.robots_disallow_all:
        manual_follow_up.append(
            "robots.txt appears to disallow broad crawling. Since you own the site this may be acceptable, but review before automating larger runs."
        )

    deduped_warnings = list(dict.fromkeys(warnings))

    return CrawlReport(
        generated_at=snapshot.generated_at,
        target_url=snapshot.target_url,
        probably_squarespace=snapshot.probe.probably_squarespace,
        version_hint=snapshot.probe.version_hint,
        pages_crawled=len(snapshot.pages),
        ok_pages=ok_pages,
        pages_with_json=pages_with_json,
        password_gated_pages=password_gated_pages,
        unique_assets=len(unique_assets),
        unique_internal_links=len(unique_internal_links),
        sitemap_entries=len(snapshot.probe.sitemap_entries),
        rss_feeds=snapshot.probe.rss_feeds,
        manual_follow_up=manual_follow_up,
        pages=page_entries,
        warnings=deduped_warnings,
    )
