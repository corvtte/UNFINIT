# UNFINIT Architecture & Spark Interaction Constitution

- Rule 1: Strict Cloud-First Execution (No local bots, daemons, or heavy bandwidth tasks).
- Rule 2: Single-Push GitHub CI/CD (Push only to GitHub with local proxy 127.0.0.1:10808; GitHub Actions mirrors to Hugging Face).
- Rule 3: Public OpSec & Code Sanitization (Strictly no target site brand names in filenames or public code symbols; use feed_crawler).
- Rule 4: UI Design System & Theme Purity (No raw emojis in templates; use SVG icons; strictly respect CSS variables for theme compatibility like Solarized Dark).
- Rule 5: Antigravity Prompt Format (Always encapsulate Antigravity instructions in exactly one single code block using 'text' without internal backticks).


### 5.26. JavaScript Syntax & DOM Event Integrity in Web Panel
Embedded JavaScript in Python web panel templates must strictly maintain 100% valid syntax with balanced braces. Ad-hoc string replacements that introduce SyntaxError and freeze dashboard buttons are strictly forbidden.

### 5.27. Reporting Format & BiDi Layout Preservation
Antigravity must conclude every execution report with a structured Markdown Summary Table (| Row | Module | Changes | Status |). In Persian explanations, all English identifiers and keywords must strictly be enclosed in backticks to prevent RTL/LTR bidirectional rendering corruption.


### 5.28. Modern Non-CMS Scraper Architecture & Session Cookie Injection
Target sites must not be assumed to run standard CMS frameworks (e.g. WordPress). Crawlers must prioritize direct session cookie injection (FEED_AUTH_COOKIE) to bypass dynamic SPA/Alpine.js authentication friction. Raw HTTP diagnostics must be logged on failure.


### 6.0. Modular Architecture & Separation of Concerns Roadmap
Monolithic 7000+ line Python templates embedding raw JavaScript strings represent a legacy anti-pattern. Going forward, complex UI components and client-side logic must be isolated into dedicated standalone files to guarantee syntax highlighting, native linter support, and prevent global dashboard regressions.


### 6.1. Incremental Component Modularization (Strangler Fig Pattern)
Whenever modifying legacy monolithic sections in web_panel.py, agents must iteratively isolate components into dedicated sub-modules. Theme styles must strictly rely on CSS variables across the 5 approved core themes.
