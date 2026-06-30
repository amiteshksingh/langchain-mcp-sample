from mcp_server.tools import add_numbers, explain_text


def test_add_numbers() -> None:
    assert add_numbers(2, 3) == 5


def test_explain_text() -> None:
    assert explain_text("Hello World") == "Explain Hello World"
