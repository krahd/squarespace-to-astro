# Media extraction limitations

Media extraction is evidence-driven and best-effort. It does not query or enumerate a creator's Vimeo or YouTube account.

A media item can remain undiscovered when:

- its page is disabled, hidden, password-protected, or absent from all crawl seeds;
- the provider configuration is created only after browser-side interaction not present in the captured source;
- the page mentions a provider but exposes neither a stable URL nor a provider video ID;
- access requires an authenticated administrative context not supplied to the crawl.

Such cases must remain explicit unresolved records or be recovered through authenticated capture and manual route comparison. They must not be silently counted as complete.
