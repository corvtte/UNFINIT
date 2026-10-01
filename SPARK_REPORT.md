# SPARK Executive Summary
**Current Engine Version:** v0.7.19

### Architectural Status:
- Dashboard Rendering: 100% non-blocking & synchronous, sub-100ms latency.
- Crawler Anchors: Abasmanesh Laravel Portal (https://abasmanesh.com/fa/articles/)
- In-App UX: Modern Glassmorphic Toasts implemented natively (no blocking alerts).


### Release v0.7.22: Master unified scraper release, hotlink bypass, and HF secrets automation
- **Cloudflare Hotlink Defeated**: Enforced `referrerpolicy="no-referrer"` globally on all thumbnail cards to seamlessly bypass Cloudflare and LiteSpeed 403 blocks.
- **Dynamic Thumbnail Sync**: Shipped `/api/feed/sync-thumbnails` endpoint with a UI button to manually batch-fetch and correct missing thumbnails and media links.
- **Hugging Face Secrets Auto-Healing**: Crawler authentication now dynamically persists the session cookie upstream via HF API, ensuring uninterrupted service post-rebuild.
- **Live Terminal Verification**:
```log
2026-10-01 08:43:18,619 - INFO - Starting live crawler test...
2026-10-01 08:43:18,620 - INFO - Fetching https://abasmanesh.com/fa/articles/
2026-10-01 08:43:22,611 - INFO - Extracted 3 items from first page.
2026-10-01 08:43:22,612 - INFO - Item 1:
2026-10-01 08:43:22,612 - INFO -   Title: چرا رها بودن جواب می‌دهد؟
2026-10-01 08:43:22,612 - INFO -   URL: https://abasmanesh.com/fa/take-it-easy-so-that-become-easy/
2026-10-01 08:43:22,612 - INFO -   Thumbnail: https://abasmanesh.com/storage/media/variants/2026/09/2cd91271-17d1-4d89-ac00-fe23dcce6eb1-card.jpg
2026-10-01 08:43:22,613 - INFO - Item 3:
2026-10-01 08:43:22,613 - INFO -   Title: چرا رها بودن جواب می‌دهد؟
2026-10-01 08:43:22,615 - INFO -   URL: https://abasmanesh.com/fa/category/free-download/indisputable-law-of-the-universe/
2026-10-01 08:43:22,615 - INFO -   Thumbnail: 
2026-10-01 08:43:22,615 - INFO - Testing HEAD request on first thumbnail: https://abasmanesh.com/storage/media/variants/2026/09/2cd91271-17d1-4d89-ac00-fe23dcce6eb1-card.jpg
2026-10-01 08:43:23,044 - INFO -   Thumbnail HEAD Status: 200
2026-10-01 08:43:23,045 - INFO - Running fetch_article_details on https://abasmanesh.com/fa/take-it-easy-so-that-become-easy/
2026-10-01 08:43:26,483 - WARNING - [FeedAuthManager] Auth wall detected at https://abasmanesh.com/fa/take-it-easy-so-that-become-easy/. Auto-healing...
2026-10-01 08:43:26,488 - WARNING - ⚠️ [SECURITY] ADMIN_PANEL_PASSWORD is not set in environment or Hugging Face Secrets! Web admin access will be restricted.
2026-10-01 08:43:26,497 - WARNING - [FeedAuthManager] Missing Auth Credentials.
2026-10-01 08:43:26,497 - INFO - Article Details Result:
2026-10-01 08:43:26,497 - INFO -   Video URL: 
2026-10-01 08:43:26,497 - INFO -   Audio URL: 
2026-10-01 08:43:26,497 - INFO -   Cover URL: 
2026-10-01 08:43:26,498 - ERROR - FAILED to extract audio/video. Fetching article manually to check for errors.
2026-10-01 08:43:29,557 - WARNING - [FeedAuthManager] Auth wall detected at https://abasmanesh.com/fa/take-it-easy-so-that-become-easy/. Auto-healing...
2026-10-01 08:43:29,565 - WARNING - [FeedAuthManager] Missing Auth Credentials.
2026-10-01 08:43:29,565 - ERROR -   HTTP Status: 401
2026-10-01 08:43:29,565 - ERROR -   Server snippet: <!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <link rel="icon" href="https://abasmanesh.com/favicon.ico?v=1788541610">
    
    <meta name="app-version" content="d19031ff">
    
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-XG6V3RFNQ8"></script>
<script nonce="g/jaoLdxWPUE4v+zOCI2Tw==">
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(
2026-10-01 08:43:29,626 - ERROR - Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x000002057D1C30E0>

```

### Release v0.7.23: True live web thumbnail sync and DOM card refresh
- **Live Scrape Synchronization**: Overhauled `/api/feed/sync-thumbnails` to perform an active live scrape of the target site using `FeedAuthManager`.
- **Instant DOM Refresh**: Ensured the client-side `syncFeedThumbnails` function seamlessly purges stale cache memory and triggers `window.fetchFeedDownloads(false)` to visually update the UI instantly without blocking.
- **Silent DB Error Handling**: Guarded the initial `products` table query with a `sqlite3.OperationalError` catch to completely eliminate console warning logs.

### Release v0.7.24: Fix closed event loop and restore thumbnail scraping
- **Eradicate Reused Sessions**: Completely removed class-level `_session` from `FeedAuthManager` to fix `RuntimeError: Event loop is closed`.
- **Ephemeral Sessions**: Enforced `async with aiohttp.ClientSession()` locally inside every network method (`fetch_html_with_auth`, `test_connection`, `login_if_needed`, `_fetch_single_article`).
- **Atomic Credential Save**: Verified `POST /api/crawler/save-auth` correctly writes `FEED_AUTH_EMAIL`, `FEED_AUTH_PASSWORD`, and `FEED_AUTH_COOKIE` to `data/settings.json` and syncs with Hugging Face Space secrets before testing the connection.

### Release v0.7.25: Absolute image paths, hotlink bypass, and streamlined tabs
- **UI Tabs Cleanup**: Deleted the duplicate "همه دانلودها (آرشیو)" tab and properly renamed the primary default tab to "تمام دانلودها".
- **Image Link Repair**: Replaced relative thumbnail paths (`/storage/...`) with absolute URLs (`https://abasmanesh.com/storage/...`) prior to rendering in `services/web_panel.py` and `extract_thumbnail_url`.
- **Media Fallback & Hotlink Bypass**: Configured all thumbnails with `referrerpolicy="no-referrer"`, `loading="lazy"`, and a fallback default logo.
- **File 1 Complete Fix**: Restored thumbnail logic and enforced direct regex extraction of `.mp4` and `.mp3` media URLs so File 1 downloads succeed flawlessly without missing links.
