# SPARK Executive Summary
**Current Engine Version:** v0.7.19

### Architectural Status:
- Dashboard Rendering: 100% non-blocking & synchronous, sub-100ms latency.
- Crawler Anchors: Abasmanesh Laravel Portal (https://abasmanesh.com/fa/articles/)
- In-App UX: Modern Glassmorphic Toasts implemented natively (no blocking alerts).


### Release v0.7.20: Auth Direct Persistence & Live Scraper Updates
- **Direct Auth API**: Deployed POST /api/crawler/save-auth for immediate credential persistence (settings.json) and live session validation.
- **Smart UI Toasts**: Replaced all native alert() calls with beautiful, non-blocking Tailwind glassmorphic toasts with deduplication logic.
- **Enhanced Laravel Media Extraction**: Live dispatch and rescrape commands now extract og:image and populate database basmanesh_feed.thumbnail_url, udio_url, and ideo_url directly.
- **Theme Polish**: Feed auth modal stripped of hardcoded white borders, fully respecting --border-color.
