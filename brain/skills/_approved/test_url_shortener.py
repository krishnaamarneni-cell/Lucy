"""Tests for url_shortener skill."""
from url_shortener import shorten_url, TOOL_META


def test_import():
    assert callable(shorten_url)
    assert TOOL_META["name"] == "url_shortener"
    assert TOOL_META["function"] is shorten_url


def test_empty_url():
    result = shorten_url()
    assert "Error" in result


def test_call():
    result = shorten_url("https://example.com/some/long/path")
    assert isinstance(result, str)
    print(f"Result preview: {result[:200]}")


if __name__ == "__main__":
    test_import()
    test_empty_url()
    test_call()
    print("\u2705 All tests passed")
