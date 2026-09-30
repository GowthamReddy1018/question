import hashlib
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import app


class PasswordResetTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.accounts = {
            "student": {
                "email": "student@example.com",
                "password_salt": "old-salt",
                "password_hash": app.hash_password("old-pass", "old-salt"),
                "api_key": "old-api-key",
            }
        }
        self.load_patch = patch.object(app, "load_accounts", return_value=self.accounts)
        self.save_patch = patch.object(app, "save_accounts")
        self.load_patch.start()
        self.save_patch.start()
        self.addCleanup(self.load_patch.stop)
        self.addCleanup(self.save_patch.stop)

    async def test_request_emails_six_digit_code_and_confirm_changes_password(self):
        with (
            patch.object(app, "smtp_configuration_error", return_value=None),
            patch.object(app.secrets, "randbelow", return_value=123456),
            patch.object(app, "send_password_reset_email", return_value=True) as send_email,
        ):
            response = await app.request_password_reset(
                app.PasswordResetRequest(email="student@example.com")
            )

        self.assertTrue(response["success"])
        send_email.assert_called_once_with("student@example.com", "123456")
        account = self.accounts["student"]
        self.assertEqual(account["password_reset_otp_hash"], hashlib.sha256(
            f'{account["password_reset_otp_salt"]}:123456'.encode("utf-8")
        ).hexdigest())
        self.assertNotIn("password_reset_otp", account)

        reset_response = await app.confirm_password_reset(
            app.PasswordResetConfirm(
                email="student@example.com",
                otp="123456",
                new_password="new-password",
            )
        )

        self.assertTrue(reset_response["success"])
        self.assertNotEqual(account["api_key"], "old-api-key")
        self.assertTrue(app.secrets.compare_digest(
            account["password_hash"],
            app.hash_password("new-password", account["password_salt"]),
        ))
        self.assertNotIn("password_reset_otp_hash", account)

    async def test_code_is_invalid_after_five_failed_attempts(self):
        with (
            patch.object(app, "smtp_configuration_error", return_value=None),
            patch.object(app.secrets, "randbelow", return_value=123456),
            patch.object(app, "send_password_reset_email", return_value=True),
        ):
            await app.request_password_reset(
                app.PasswordResetRequest(email="student@example.com")
            )

        for _ in range(5):
            with self.assertRaises(HTTPException):
                await app.confirm_password_reset(
                    app.PasswordResetConfirm(
                        email="student@example.com",
                        otp="000000",
                        new_password="new-password",
                    )
                )

        self.assertNotIn("password_reset_otp_hash", self.accounts["student"])
        with self.assertRaises(HTTPException):
            await app.confirm_password_reset(
                app.PasswordResetConfirm(
                    email="student@example.com",
                    otp="123456",
                    new_password="new-password",
                )
            )

    async def test_request_response_does_not_disclose_unknown_email(self):
        with (
            patch.object(app, "smtp_configuration_error", return_value=None),
            patch.object(app, "send_password_reset_email") as send_email,
        ):
            response = await app.request_password_reset(
                app.PasswordResetRequest(email="unknown@example.com")
            )

        self.assertEqual(response["message"], (
            "If an account matches and email recovery is configured, "
            "a verification code will arrive shortly."
        ))
        send_email.assert_not_called()

    async def test_request_reports_missing_smtp_configuration(self):
        with patch.object(
            app,
            "smtp_configuration_error",
            return_value="Email delivery is not configured. Set SMTP credentials in .env.",
        ):
            with self.assertRaises(HTTPException) as error:
                await app.request_password_reset(
                    app.PasswordResetRequest(email="student@example.com")
                )

        self.assertEqual(error.exception.status_code, 503)
        self.assertIn(".env", error.exception.detail)

    async def test_request_explains_gmail_authentication_failure(self):
        with (
            patch.object(app, "smtp_configuration_error", return_value=None),
            patch.object(app, "send_password_reset_email", side_effect=app.smtplib.SMTPAuthenticationError(535, b"Bad credentials")),
        ):
            with self.assertRaises(HTTPException) as error:
                await app.request_password_reset(
                    app.PasswordResetRequest(email="student@example.com")
                )

        self.assertEqual(error.exception.status_code, 502)
        self.assertIn("16-character Google App Password", error.exception.detail)
        self.assertNotIn("password_reset_otp_hash", self.accounts["student"])

    def test_gmail_password_must_be_a_16_character_app_password(self):
        with (
            patch.object(app, "load_dotenv"),
            patch.dict("os.environ", {
                "SMTP_HOST": "smtp.gmail.com",
                "SMTP_PORT": "587",
                "SMTP_FROM": "sender@example.com",
                "SMTP_USERNAME": "sender@example.com",
                "SMTP_PASSWORD": "not-a-real-gmail-password",
            }, clear=False),
        ):
            error = app.smtp_configuration_error()

        self.assertIsNotNone(error)
        self.assertIn("16-character Google App Password", error)

    def test_gmail_app_password_accepts_grouped_spaces(self):
        with (
            patch.object(app, "load_dotenv"),
            patch.dict("os.environ", {
                "SMTP_HOST": "smtp.gmail.com",
                "SMTP_PORT": "587",
                "SMTP_FROM": "sender@example.com",
                "SMTP_USERNAME": "sender@example.com",
                "SMTP_PASSWORD": "abcd efgh ijkl mnop",
            }, clear=False),
        ):
            error = app.smtp_configuration_error()

        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
