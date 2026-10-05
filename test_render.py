import sys
import json
import logging
from services.web_panel import render_dashboard_html

try:
    html = render_dashboard_html()
    with open('rendered_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Dashboard rendered and saved to rendered_dashboard.html")
except Exception as e:
    print(f"Error rendering dashboard: {e}")
