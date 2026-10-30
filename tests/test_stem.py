"""Tests for the stemmer."""

from src.agent.stem import stem


def test_long_word_truncated():
    assert stem("установить") == "устан"
    assert stem("установка") == "устан"
    assert stem("документы") == "докум"
    assert stem("документ") == "докум"


def test_short_word_unchanged():
    assert stem("16") == "16"
    assert stem("гб") == "гб"
    assert stem("озу") == "озу"
    assert stem("покуп") == "покуп"


def test_boundary_length_5_unchanged():
    assert stem("банка") == "банка"
    assert stem("банки") == "банки"


def test_boundary_length_6_truncated():
    assert stem("банков") == "банко"
    assert stem("памяти") == "памят"