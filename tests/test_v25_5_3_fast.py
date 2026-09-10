import py_compile
import unittest
from services.web_panel import render_dashboard_html, render_storefront_html
from core.config import config

class TestV2553Fast(unittest.TestCase):
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
        self.assertIn('toggleAdminLoginPwd', html)
        self.assertIn('executeAdminLogin', html)
        self.assertIn('applySuccessfulLogin', html)
        self.assertIn('checkAdminLoginOnLoad', html)
        self.assertIn('window.handleLoginSubmit = executeAdminLogin;', html)
        self.assertIn('v0.1.0', html)

    def test_storefront_version(self):
        store_html = render_storefront_html()
        self.assertIn('v0.1.0', store_html)

    def test_api_login_logic(self):
        from app import verify_admin_password, get_valid_admin_passwords
        self.assertFalse(verify_admin_password(""))
        self.assertFalse(verify_admin_password(None))
        self.assertFalse(verify_admin_password("totally_invalid_password_999999"))
        valid = get_valid_admin_passwords()
        if valid:
            sample_pwd = next(iter(valid))
            self.assertTrue(verify_admin_password(sample_pwd))

if __name__ == "__main__":
    unittest.main()
