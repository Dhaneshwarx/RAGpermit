"""Keep reviewed Markdown sections, including tables and notes, together."""
import re
from src.section_refs import section_references

MAX_SECTION_CHARS = 8000
HEADING = re.compile(r"^ {0,3}##\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^ {0,3}([" + chr(96) + r"]{3,}|~{3,})")


def split_into_sections(body_text):
    if not isinstance(body_text, str):
        raise ValueError("Document body must be text.")
    sections, lines = [], []
    title = "Overview"
    fence_char, fence_length = None, 0

    def append_section():
        text = "\n".join(lines).strip()
        if not text:
            return
        if len(text) > MAX_SECTION_CHARS:
            raise ValueError("Section exceeds 8000 characters: " + title +
                             ". Split at a logical boundary, keeping table headers and notes.")
        sections.append((title, text))

    for line in body_text.splitlines():
        marker = FENCE.match(line)
        if fence_char is not None:
            lines.append(line)
            if marker and marker.group(1)[0] == fence_char and len(marker.group(1)) >= fence_length and not line[marker.end():].strip():
                fence_char = None
            continue
        if marker:
            fence_char, fence_length = marker.group(1)[0], len(marker.group(1))
            lines.append(line)
            continue
        heading = HEADING.match(line)
        if heading:
            append_section()
            title, lines = heading.group(1), []
        else:
            lines.append(line)
    if fence_char is not None:
        raise ValueError("Unclosed Markdown code fence.")
    append_section()
    return sections


def make_chunks(document):
    header = document["header"]
    chunks = []
    for number, (title, text) in enumerate(split_into_sections(document["body"]), 1):
        # Subheadings stay with their parent so qualifications remain visible.
        refs = section_references(title, heading=True)
        fence_char, fence_length = None, 0
        for line in text.splitlines():
            marker = FENCE.match(line)
            if fence_char is not None:
                if marker and marker.group(1)[0] == fence_char and len(marker.group(1)) >= fence_length and not line[marker.end():].strip():
                    fence_char = None
                continue
            if marker:
                fence_char, fence_length = marker.group(1)[0], len(marker.group(1))
                continue
            subheading = re.match(r"^ {0,3}#{3,6}\s+(.+)", line)
            if subheading:
                refs.extend(section_references(subheading.group(1), heading=True))
        chunks.append({
            "chunk_id": header["doc_id"] + "#" + str(number),
            "doc_id": header["doc_id"], "title": header["title"],
            "section": title, "text": text, "section_refs": sorted(set(refs)),
            "clearance": header["clearance"], "department": header["department"],
            "allowed_roles": header["allowed_roles"],
        })
    return chunks
