"""Explicit section identifiers; digits and subsection suffixes stay exact."""
import re

IDENTIFIER = r"[0-9]+(?:\.[0-9]+)*(?:\s*\([a-z0-9]+\))*"
IDENTIFIER_LIST = IDENTIFIER + r"(?:\s*(?:,|\band\b|\bor\b|&)\s*" + IDENTIFIER + r")*"
MENTION = re.compile(r"(?:\bsections?\s+|\bsec\.\s*|§\s*)(" + IDENTIFIER_LIST + r")(?![\w(]|\.\d)", re.I)
HEADING = re.compile(r"^\s*(" + IDENTIFIER + r")(?=\s|[.:—-]|$)", re.I)


def section_references(text, heading=False):
    values = []
    for match in MENTION.finditer(text):
        if re.match(r"\s*(?:[-–—]|to\b|through\b)\s*\d", text[match.end():], re.I):
            raise ValueError("List section numbers individually; ranges are not supported.")
        values.extend(re.findall(IDENTIFIER, match.group(1), re.I))
    if heading:
        for part in text.split(" / "):
            match = HEADING.match(part)
            if match:
                values.append(match.group(1))
    return sorted({re.sub(r"\s+", "", value).lower() for value in values})


def query_references(question):
    current = question.split("\nEarlier user questions, oldest first:", 1)[0]
    return section_references(current) or section_references(question)
