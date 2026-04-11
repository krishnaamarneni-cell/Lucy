"""Tests for the quotable Lucy skill."""
from quotable import get_random_quote, TOOL_META


def test_import():
    assert callable(get_random_quote)
    assert TOOL_META["name"] == "quotable"
    assert TOOL_META["function"] is get_random_quote
    print("test_import passed")


def test_call():
    result = get_random_quote()
    assert isinstance(result, str)
    assert len(result) > 0
    print(f"Result preview: {result[:200]}")


def test_with_tag():
    result = get_random_quote(tag="wisdom")
    assert isinstance(result, str)
    assert len(result) > 0
    print(f"Tagged result preview: {result[:200]}")


def test_error_handling():
    # Should return error string, never raise
    result = get_random_quote(tag="nonexistent_tag_xyz_999")
    assert isinstance(result, str)
    print(f"Error handling result: {result[:200]}")


if __name__ == "__main__":
    test_import()
    test_call()
    test_with_tag()
    test_error_handling()
    print("\u2705 All tests passed")
