import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.unit
def test_gemini_returns_non_empty_response():
    """Agent must return a non-empty string for any prompt."""
    with patch("scripts.verify_connection.Agent") as MockAgent:
        mock_instance = MagicMock()
        mock_instance.run.return_value = MagicMock(content="Hello from Gemini")
        MockAgent.return_value = mock_instance

        from scripts.verify_connection import check_connection

        result = check_connection()

        assert result is not None
        assert len(result) > 0


@pytest.mark.unit
def test_gemini_raises_on_missing_api_key():
    """Should raise EnvironmentError when GOOGLE_API_KEY is absent."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
            from scripts.verify_connection import check_connection

            check_connection()
