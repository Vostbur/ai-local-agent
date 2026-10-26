from src.agent.tools._search import find_match, find_match_with_kind


class TestFindMatchExact:
    def test_exact_match(self):
        result = find_match("Список покупок", "покупок")
        assert result == (7, 14)

    def test_exact_match_returns_kind(self):
        result = find_match_with_kind("Список покупок", "покупок")
        assert result is not None
        assert result[2] == "exact"


class TestFindMatchCaseInsensitive:
    def test_case_insensitive(self):
        result = find_match("Список Покупок", "покупок")
        assert result is not None


class TestFindMatchStem:
    def test_stem_match(self):
        result = find_match("Сделать для документов", "документы")
        assert result is not None

    def test_stem_kind(self):
        _, _, kind = find_match_with_kind("Сделать для документов", "документы")
        assert kind == "stem"

    def test_short_query_no_stem(self):
        result = find_match("стол", "столы")
        assert result is None


class TestFindMatchNoMatch:
    def test_no_match(self):
        result = find_match("Завтра встреча", "проекта")
        assert result is None


class TestFindMatchEmptyQuery:
    def test_empty_query(self):
        result = find_match("текст", "")
        assert result is None
