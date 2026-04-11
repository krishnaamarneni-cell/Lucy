"""Tests for reddit_top skill."""
from reddit_top import get_reddit_top, TOOL_META


def test_import():
    assert callable(get_reddit_top)
    assert TOOL_META["name"] == "reddit_top"
    assert TOOL_META["function"] is get_reddit_top


def test_call():
    result = get_reddit_top("SAP", 5)
    assert isinstance(result, str)
    assert len(result) > 0
    print(f"Result preview:\n{result[:500]}")


def test_default_params():
    result = get_reddit_top()
    assert isinstance(result, str)
    print(f"Default call preview:\n{result[:300]}")


def test_invalid_subreddit():
    result = get_reddit_top("thisisnotarealsubreddit99999")
    assert isinstance(result, str)
    assert "Error" in result or "No top posts" in result
    print(f"Invalid subreddit result: {result}")


if __name__ == "__main__":
    test_import()
    print("test_import passed")
    test_call()
    print("test_call passed")
    test_default_params()
    print("test_default_params passed")
    test_invalid_subreddit()
    print("test_invalid_subreddit passed")
    print("\nAll tests passed")
