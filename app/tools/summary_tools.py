"""Text tools. summarize_text is extractive (picks the most important sentences), so it is
deterministic, free and fast, and never sends the text to another service."""

import re
from collections import Counter

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"\b[\w'-]+\b")

_STOPWORDS = frozenset(
    """a about above after again against all am an and any are as at be because been before
    being below between both but by can could did do does doing down during each few for from
    further had has have having he her here hers herself him himself his how i if in into is it
    its itself just me more most my myself no nor not now of off on once only or other our ours
    ourselves out over own same she should so some such than that the their theirs them
    themselves then there these they this those through to too under until up very was we were
    what when where which while who whom why will with would you your yours yourself yourselves
    also""".split()
)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def _words(text: str) -> list[str]:
    return _WORD.findall(text)


def count_words(text: str) -> dict:
    return {
        "word_count": len(_words(text)),
        "character_count": len(text),
        "character_count_without_spaces": len(re.sub(r"\s", "", text)),
        "sentence_count": len(_sentences(text)),
    }


def summarize_text(text: str, max_sentences: int = 3) -> dict:
    sentences = _sentences(text)
    original_words = len(_words(text))

    if len(sentences) <= max_sentences:
        chosen = sentences
    else:
        frequencies = Counter(
            w.lower() for w in _words(text) if w.lower() not in _STOPWORDS and len(w) > 2
        )

        def score(sentence: str) -> float:
            words = [w.lower() for w in _words(sentence)]
            if not words:
                return 0.0
            return sum(frequencies.get(w, 0) for w in words) / len(words)

        ranked = sorted(range(len(sentences)), key=lambda i: score(sentences[i]), reverse=True)
        keep = sorted(ranked[:max_sentences])  # restore original order
        chosen = [sentences[i] for i in keep]

    summary = " ".join(chosen)
    return {
        "summary": summary,
        "original_word_count": original_words,
        "summary_word_count": len(_words(summary)),
        "original_sentence_count": len(sentences),
        "summary_sentence_count": len(chosen),
    }
