# Media extraction

`crawl` and `migrate` extract Vimeo and YouTube references from both rendered page HTML and opportunistic Squarespace JSON payloads.

The crawler records media in two places:

- each page in `site_snapshot.json` contains `media` and `unresolved_media` arrays;
- `media_manifest.json` provides a flat site-wide inventory grouped by owner route.

For each resolved reference, the inventory records:

- provider;
- provider video ID;
- original source URL;
- canonical embed URL;
- source kinds and detection methods;
- confidence and occurrence count;
- Vimeo privacy token, when present.

Vimeo privacy tokens are significant for unlisted videos. Migrations must preserve the token and full canonical embed URL rather than retaining only the numeric Vimeo ID.

`media_manifest.json` also records provider mentions for which no stable video ID could be extracted. These are not successful captures and require manual review. A zero unresolved count does not prove that hidden or administratively disabled pages were discovered; normal route-completeness checks still apply.
