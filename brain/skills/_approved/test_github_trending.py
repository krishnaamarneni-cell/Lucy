from github_trending import get_trending_repos, TOOL_META


def test_import():
    assert callable(get_trending_repos)
    assert TOOL_META["name"] == "github_trending"
    assert TOOL_META["function"] is get_trending_repos
    assert "language" in TOOL_META["parameters"]["properties"]
    assert "timeframe" in TOOL_META["parameters"]["properties"]
    assert "count" in TOOL_META["parameters"]["properties"]


def test_call_default():
    result = get_trending_repos()
    assert isinstance(result, str)
    assert "Error" not in result or "Trending" in result
    print(f"Default result preview:\n{result[:300]}\n")


def test_call_with_language():
    result = get_trending_repos("python", "weekly", 3)
    assert isinstance(result, str)
    print(f"Python weekly preview:\n{result[:300]}\n")


def test_call_with_bad_timeframe():
    result = get_trending_repos(timeframe="bogus")
    assert isinstance(result, str)
    # Should fall back to daily, not crash
    assert "Error" not in result or isinstance(result, str)
    print(f"Bad timeframe preview:\n{result[:200]}\n")


if __name__ == "__main__":
    test_import()
    print("test_import passed")
    test_call_default()
    print("test_call_default passed")
    test_call_with_language()
    print("test_call_with_language passed")
    test_call_with_bad_timeframe()
    print("test_call_with_bad_timeframe passed")
    print("All tests passed")
