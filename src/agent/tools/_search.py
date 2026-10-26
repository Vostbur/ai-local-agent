from typing import Optional, Tuple


def find_match_with_kind(
    text: str,
    query: str,
    *,
    min_stem_len: int = 5,
) -> Optional[Tuple[int, int, str]]:
    if not text or not query.strip():
        return None

    text_l = text.lower()
    query_l = query.lower()

    if query_l in text_l:
        start = text_l.index(query_l)
        return (start, start + len(query_l), "exact")

    if len(query_l) >= min_stem_len:
        stem = query_l[:-2]
        if len(stem) >= min_stem_len - 1 and stem in text_l:
            start = text_l.index(stem)
            return (start, start + len(stem), "stem")

    return None


def find_match(
    text: str,
    query: str,
    *,
    min_stem_len: int = 5,
) -> Optional[Tuple[int, int]]:
    res = find_match_with_kind(text, query, min_stem_len=min_stem_len)
    return res[:2] if res is not None else None
