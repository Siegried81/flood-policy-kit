"""Translate an approved brief section, and prove the figures survived.

The brief is drafted in English because the corpus, the UI and the code are in
English and a jury reads it there. But the authority that would act on it is
Belgian, and a Walloon or Flemish official reads a recommendation in French or in
Dutch. So translation is a tab, never a rewrite: the English section stays the
record and the translation sits beside it.

**Why this module exists at all, rather than a line of prompt.** A translation is
the one transformation in this kit that is allowed to change every word and
forbidden to change a single number. A model asked to translate a paragraph will
cheerfully localise `29,727,887` to `29 727 887` - which is correct - and just as
cheerfully write `29,7 million`, drop a citation marker, or round `16.9%` to
`17%`. None of that looks wrong in the output. So every translation is checked
against its source, and one that lost a figure or a citation is returned with the
failure named rather than displayed.

**Separators are the trap inside the trap.** English writes `1,345`, French
writes `1 345`, Dutch writes `1.345`, and the same three characters mean
thousands in one language and a decimal point in another. Comparing the strings
would flag every correct translation; comparing the parsed numbers would need a
locale this module does not know. So the comparison is on the DIGITS alone, in
order: `29,727,887` and `29 727 887` are both `29727887`, while `29,7 million`
is `297` and fails.

One structured call per section, same provider path as the drafting step, so a
dead venue network falls back to the local model here too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.rag import complete

#: The languages a Belgian authority actually works in. English is the source and
#: so is not a target: offering it would invite a round trip, and a translation of
#: a translation is how a figure quietly changes.
LANGUAGES = {
    "fr": "French",
    "nl": "Dutch",
    "de": "German",
}

SYSTEM_PROMPT = (
    "You translate one section of a policy brief for a public authority. "
    "Translate the prose faithfully into {language}, in the register a civil "
    "servant would use. Keep EVERY number exactly as it is: do not round, do not "
    "convert units, do not write a figure out in words. You may use the thousands "
    "and decimal separators of {language}. Keep every citation marker such as "
    "[S1] or [S2] exactly where it is. Keep place names, region names and "
    "institution names in their original form. Output the translation only, with "
    "no preamble and no note about what you did."
)

#: `[S1]`, `[S12]` - the marker the drafting step emits and the verify step counts.
_CITATION = re.compile(r"\[S\d+\]")

#: A run of digits, together with the separators that sit BETWEEN digits. The
#: lookarounds are what make `1,345` one token and `[S1], [S2]` two.
_NUMBER = re.compile(r"\d+(?:[ .,  ](?=\d)\d+)*")


class TranslationFailed(RuntimeError):
    """The translation came back, and it is not safe to show.

    Its own type so a UI can say which figure moved instead of rendering a
    paragraph that reads perfectly and is wrong.
    """


@dataclass(frozen=True)
class Translation:
    """A translated section and the evidence it is faithful."""

    text: str
    language: str
    numbers: int
    citations: int


def digits(text: str) -> list[str]:
    """Every number in the text, reduced to its digits, in order.

    Separators between digits are dropped rather than interpreted, because which
    of `.` and `,` is the decimal point depends on the language and this module
    translates into three of them. What survives is what must not change: the
    digit sequence.

    Citation markers are removed first. `[S1]` holds a digit, and counting it as
    a figure would make every citation look like a lost number the moment one
    moved - and would report a citation fault as a figure fault, which sends a
    reader looking in the wrong place.
    """
    text = _CITATION.sub(" ", text)
    return ["".join(ch for ch in m.group() if ch.isdigit())
            for m in _NUMBER.finditer(text)]


def citations(text: str) -> list[str]:
    """Every citation marker, in order. Order matters: a brief cites per claim."""
    return _CITATION.findall(text)


def check(source: str, translated: str) -> None:
    """Raise unless every figure and every citation survived, in order.

    Deliberately strict about order as well as membership. A model that swaps two
    sentences also swaps their citations, and the result attributes each claim to
    the other's source - which no count of markers would catch.
    """
    want, got = digits(source), digits(translated)
    if want != got:
        lost = [d for d in want if d not in got]
        added = [d for d in got if d not in want]
        # The count is reported only when it actually differs. When it matches
        # and the values do not - a rounded figure, the common case - leading
        # with "2 numbers became 2 numbers" reads like a bug in the check.
        detail = (
            f" Missing: {lost[:5]}." if lost else ""
        ) + (f" Invented: {added[:5]}." if added else "")
        counts = (
            f" Source has {len(want)} numbers, the translation {len(got)}."
            if len(want) != len(got) else ""
        )
        raise TranslationFailed(
            "The figures changed." + counts + detail
            + " Nothing is shown rather than a figure nobody can trace."
        )
    want, got = citations(source), citations(translated)
    if want != got:
        raise TranslationFailed(
            f"The citations changed: {want} became {got}. Every claim in a brief "
            f"is cited to a numbered passage, so a reordered marker points the "
            f"reader at the wrong source."
        )


def translate(text: str, language: str) -> Translation:
    """One section into one language, checked before it is returned.

    `language` is a key of `LANGUAGES`, not a free-text name: a typo would reach
    the model as an instruction and come back as something plausible in a language
    nobody asked for.
    """
    if language not in LANGUAGES:
        raise ValueError(
            f"`{language}` is not a target language. Choose one of "
            f"{sorted(LANGUAGES)} - English is the source and is not a target."
        )
    if not text or not text.strip():
        raise ValueError("There is nothing to translate; draft the section first.")

    name = LANGUAGES[language]
    answer = complete(text, SYSTEM_PROMPT.format(language=name)).strip()
    if not answer:
        raise TranslationFailed(
            f"The model returned nothing for {name}. The English section is "
            f"unchanged; try again or show it as it is."
        )
    check(text, answer)
    return Translation(
        text=answer,
        language=language,
        numbers=len(digits(text)),
        citations=len(citations(text)),
    )
