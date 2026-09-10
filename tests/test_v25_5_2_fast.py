import py_compile
import unittest
from services.web_panel import render_dashboard_html, render_storefront_html
from core.config import config

class TestV2552Fast(unittest.TestCase):
    def test_compilation(self):
        py_compile.compile("app.py", doraise=True)
        py_compile.compile("services/web_panel.py", doraise=True)
        py_compile.compile("platforms/rubika_adapter.py", doraise=True)

    def test_login_gate_structure(self):
        html = render_dashboard_html()
        self.assertNotIn('<form id="mainLoginForm"', html)
        self.assertIn('id="mainLoginContainer"', html)
        self.assertIn('id="adminPasswordInput"', html)
        self.assertIn('id="loginBtn"', html)
        self.assertIn('id="loginErrorMsg"', html)
        self.assertIn('handleLoginSubmit', html)

    def test_storefront_version(self):
        store_html = render_storefront_html()
        self.assertIn('v25.5.2', store_html)

    def test_api_login_logic(self):
        from app import verify_admin_password
        self.assertFalse(verify_admin_password("unfinit2026"))
        self.assertFalse(verify_admin_password("invalid_password_123"))

if __name__ == "__main__":
    unittest.main()
