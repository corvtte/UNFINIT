"""
Hermes Agent Adapter (Aliased to Lightweight AIAgentService)
Provides transparent compatibility for web panel and telegram endpoints.
"""

from services.ai_agent_service import ai_agent_service

# Direct export for compatibility
hermes_agent = ai_agent_service

class HermesTools:
    @staticmethod
    def extract_city(text: str) -> str:
        text = str(text).lower()
        if "مشهد" in text: return "mashhad"
        if "اصفهان" in text: return "isfahan"
        if "شیراز" in text: return "shiraz"
        if "تبریز" in text: return "tabriz"
        return "tehran"
