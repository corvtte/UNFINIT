# UNFINIT Architecture & Spark Interaction Constitution

- Rule 1: Strict Cloud-First Execution (No local bots, daemons, or heavy bandwidth tasks).
- Rule 2: Single-Push GitHub CI/CD (Push only to GitHub with local proxy 127.0.0.1:10808; GitHub Actions mirrors to Hugging Face).
- Rule 3: Public OpSec & Code Sanitization (Strictly no target site brand names in filenames or public code symbols; use feed_crawler).
- Rule 4: UI Design System & Theme Purity (No raw emojis in templates; use SVG icons; strictly respect CSS variables for theme compatibility like Solarized Dark).
- Rule 5: Antigravity Prompt Format (Always encapsulate Antigravity instructions in exactly one single code block using 'text' without internal backticks).
