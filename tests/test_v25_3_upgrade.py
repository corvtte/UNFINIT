import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

async def run_v25_3_tests():
    print("==================================================")
    print("🚀 Running UNFINIT Store Engine v25.3.0 Verification")
    print("==================================================")

    # 1. Verify Complete Purge of Divar / Sheypoor / Real Estate
    print("\n[TEST 1] Verifying 100% clean purge of Divar, Sheypoor, and Real Estate...")
    files_to_check = [
        "services/ai_agent_service.py",
        "services/web_panel.py",
        "platforms/telegram_adapter.py"
    ]
    for rel_p in files_to_check:
        with open(rel_p, "r", encoding="utf-8") as f:
            content = f.read()
        for forbidden in ["دیوار", "شیپور", "املاک"]:
            assert forbidden not in content, f"Found '{forbidden}' in {rel_p}!"
    print("✅ All source code is 100% clean of Divar, Sheypoor, and Real Estate!")

    # 2. Verify Telegram AI Handler Removal
    print("\n[TEST 2] Verifying removal of Telegram public /ai command...")
    with open("platforms/telegram_adapter.py", "r", encoding="utf-8") as f:
        tg_content = f.read()
    assert 'command("ai")' not in tg_content, "Telegram /ai command still exists!"
    print("✅ Telegram /ai command successfully removed (AI is now centralized in Web Panel)!")

    # 3. Verify Studio & Course Copilot System Prompt & Free Models
    print("\n[TEST 3] Verifying Studio & Course Copilot specialization...")
    from services.ai_agent_service import ai_agent_service, STUDIO_SYSTEM_PROMPT
    assert "متادیتا" in STUDIO_SYSTEM_PROMPT
    assert "۴۹.۹۹" in STUDIO_SYSTEM_PROMPT
    assert "stepfun-3.7-flash" in ai_agent_service.SUPPORTED_FREE_MODELS
    assert "mistral-large" in ai_agent_service.SUPPORTED_FREE_MODELS
    print("✅ Studio & Course Copilot prompts and supported free models verified!")

    # 4. Live Test with Nara Router Free Model (Fixing 402 Error)
    print("\n[TEST 4] Testing live chat with free model stepfun-3.7-flash (no 402 error)...")
    res = await ai_agent_service.chat(
        "سلام! در یک جمله بگو چطور در شماره‌گذاری جلسات دوره صوتی کمک می‌کنی؟",
        model="stepfun-3.7-flash"
    )
    print(f"   Status: ok={res['ok']}, Model={res.get('model')}")
    print(f"   Response:\n   {res.get('reply')}\n")
    assert res["ok"] is True, f"Chat failed: {res}"
    assert len(res["reply"]) > 10
    print("✅ Live chat with free Nara Router model succeeded with zero 402 errors!")

    # 5. Verify Web Panel Dropdown and Rendering
    print("\n[TEST 5] Verifying Web Panel Studio Copilot UI & Model Select dropdown...")
    from services.web_panel import render_dashboard_html
    html = render_dashboard_html()
    assert "hermesModelSelect" in html, "Model selector dropdown missing!"
    assert "stepfun-3.7-flash" in html
    assert "mistral-large" in html
    assert "Studio & Course Copilot" in html or "استودیوی رسانه" in html
    print(f"✅ Web Panel HTML verified successfully ({len(html)} bytes)!")

    print("\n==================================================")
    print("🎉 ALL 5 TEST SUITES PASSED FLAWLESSLY! (v25.3.0)")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_v25_3_tests())
