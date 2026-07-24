# Media extraction validation scope

The automated regression suite covers:

- direct Vimeo player iframes;
- Vimeo unlisted privacy hashes in query strings and URL paths;
- encoded Vimeo configuration in Squarespace JSON;
- YouTube and YouTube-nocookie embed URLs;
- standard `youtube.com/watch?v=` URLs;
- watch URLs with preceding query parameters;
- escaped URLs inside JSON HTML fields;
- structured provider/video-ID pairs;
- HTML and JSON deduplication;
- unresolved provider mentions;
- crawl-level `media_manifest.json` generation;
- media counts in crawl reports.

The Laurenzo migration remains the real-site acceptance case. Its next crawl should be compared against the known project list and the `krahd` Vimeo and YouTube accounts. Unlisted media must be validated from captured page source rather than public account listings alone.
