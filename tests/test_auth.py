import os
import sys
from unittest.mock import MagicMock, mock_open, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import auth


class TestLoadCredentials:
    @patch("auth.os.path.exists", return_value=False)
    def test_returns_none_when_no_token_file(self, mock_exists):
        result = auth.load_credentials()
        assert result is None

    @patch("auth.os.path.exists", return_value=True)
    @patch("auth.Credentials.from_authorized_user_file")
    def test_returns_creds_when_valid(self, mock_from_file, mock_exists):
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_from_file.return_value = mock_creds

        result = auth.load_credentials()
        assert result is mock_creds

    @patch("auth.os.path.exists", return_value=True)
    @patch("auth.Credentials.from_authorized_user_file")
    @patch("auth._save_token")
    def test_refreshes_expired_token(self, mock_save, mock_from_file, mock_exists):
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_tok"
        mock_from_file.return_value = mock_creds

        result = auth.load_credentials()
        mock_creds.refresh.assert_called_once()
        mock_save.assert_called_once_with(mock_creds)
        assert result is mock_creds

    @patch("auth.os.path.exists", return_value=True)
    @patch("auth.Credentials.from_authorized_user_file")
    def test_returns_none_on_refresh_error(self, mock_from_file, mock_exists):
        from google.auth.exceptions import RefreshError

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_tok"
        mock_creds.refresh.side_effect = RefreshError("token revoked")
        mock_from_file.return_value = mock_creds

        result = auth.load_credentials()
        assert result is None

    @patch("auth.os.path.exists", return_value=True)
    @patch("auth.Credentials.from_authorized_user_file")
    def test_returns_none_when_not_expired_and_not_valid(self, mock_from_file, mock_exists):
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = False
        mock_from_file.return_value = mock_creds

        result = auth.load_credentials()
        assert result is None


class TestRunAuthFlow:
    @patch("auth.os.path.exists", return_value=False)
    def test_returns_none_when_no_credentials_file(self, mock_exists):
        result = auth.run_auth_flow()
        assert result is None

    @patch("auth._save_token")
    @patch("auth.InstalledAppFlow.from_client_secrets_file")
    @patch("auth.os.path.exists", return_value=True)
    def test_runs_flow_and_saves(self, mock_exists, mock_flow_cls, mock_save):
        mock_flow = MagicMock()
        mock_creds = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds
        mock_flow_cls.return_value = mock_flow

        result = auth.run_auth_flow()

        mock_flow.run_local_server.assert_called_once_with(port=0)
        mock_save.assert_called_once_with(mock_creds)
        assert result is mock_creds


class TestSaveToken:
    @patch("builtins.open", mock_open())
    def test_save_token_writes_json(self):
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "abc"}'

        auth._save_token(mock_creds)

        mock_creds.to_json.assert_called_once()
