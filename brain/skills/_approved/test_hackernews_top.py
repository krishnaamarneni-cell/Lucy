"""Tests for hackernews_top skill"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from hackernews_top import main_function, get_top_hn_stories, TOOL_META


def test_import():
    assert callable(main_function)
    assert callable(get_top_hn_stories)
    assert TOOL_META["name"] == "hackernews_top"
    assert TOOL_META["function"] is main_function
    print("test_import passed")


def test_call():
    result = main_function("3")
    assert isinstance(result, str)
    assert "Error" not in result or "HackerNews" in result
    print(f"Result preview: {result[:300]}")
    print("test_call passed")


def test_bad_input():
    result = main_function("notanumber")
    assert isinstance(result, str)
    print("test_bad_input passed")


if __name__ == "__main__":
    test_import()
    test_call()
    test_bad_input()
    print("All tests passed")
