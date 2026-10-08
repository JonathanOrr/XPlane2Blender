"""
The parameters of a lights.txt light that is typed by hand are one line of text, such as
"1 0.8 0.6 0 20000cd 0 0 -1 0.5": a value for each name of the light's LIGHT_PARAM_DEF in order
("R G B INDEX INTENSITY DX DY DZ WIDTH"), and perhaps a comment after them. This reads and changes single values of
that line without touching the rest of it.
"""

import re
from typing import Dict, List, Sequence, Tuple

# Parameters that are no setting: the light takes the same value there every time
FIXED = {"ZERO": "0", "NEG_ONE": "-1", "ONE": "1", "UNUSED": "0", "LEGACY_SIZE": "0"}
# What a value that is not there yet starts as. Everything else starts as 0
DEFAULTS = {
    "R": "1",
    "G": "1",
    "B": "1",
    "A": "1",
    "WIDTH": "1",
    "SIZE": "1",
    "INTENSITY": "20000cd",
}

_WORD = re.compile(r"\S+")


def canonical(name: str) -> str:
    """ZERO_ and ZERO__ are the second and third ZERO of a light"""
    return name.rstrip("_")


def is_fixed(name: str) -> bool:
    return canonical(name) in FIXED


def default_word(name: str) -> str:
    base = canonical(name)
    return FIXED.get(base) or DEFAULTS.get(base, "0")


def default_line(formal: Sequence[str]) -> str:
    return " ".join(default_word(name) for name in formal)


def split_line(line: str, count: int) -> Tuple[List[str], str]:
    """The first count words of a parameter line, and the comment after them (empty when there are fewer words)"""
    words, end = [], 0
    for match in _WORD.finditer(line):
        if len(words) == count:
            break
        words.append(match.group())
        end = match.end()
    return words, line[end:].strip() if len(words) == count else ""


def number(word: str) -> float:
    """20000cd is 20000, and anything that is no number is 0"""
    text = word[:-2] if word.endswith("cd") else word
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return 0.0


def values_of(line: str, formal: Sequence[str]) -> Dict[str, float]:
    """The value of each parameter in the line, the starting value for one that is not there yet"""
    words, _ = split_line(line, len(formal))
    words += [default_word(name) for name in formal[len(words) :]]
    return {canonical(name): number(word) for name, word in zip(formal, words)}


def _word_for(value: float, like: str) -> str:
    """A value as text, with the 'cd' the value it replaces had"""
    return f"{value:.6g}" + ("cd" if like.endswith("cd") else "")


def update_line(line: str, formal: Sequence[str], changes: Dict[str, float]) -> str:
    """
    The line with these parameters (by canonical name) set to new values. The rest of it stays as it was, values that
    are not different keep how they were typed, and a line with too few values is filled up with starting values
    """
    words, comment = split_line(line, len(formal))
    words += [default_word(name) for name in formal[len(words) :]]
    for i, name in enumerate(formal):
        value = changes.get(canonical(name))
        # The settings are single precision, so a value that is the same to that precision is the same
        if value is not None and abs(number(words[i]) - value) > 1e-6 * max(
            1.0, abs(value)
        ):
            words[i] = _word_for(value, words[i])
    return " ".join(words + ([comment] if comment else []))
