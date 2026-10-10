def split_into_sections(body_text):
    # A section starts at a "## " heading. Text before the first heading is "Overview".
    sections = []
    section_title = "Overview"
    section_lines = []

    for line in body_text.split("\n"):
        if line.startswith("## "):
            sections.append((section_title, "\n".join(section_lines).strip()))
            section_title = line[3:].strip()
            section_lines = []
        else:
            section_lines.append(line)

    sections.append((section_title, "\n".join(section_lines).strip()))

    # Drop sections with no text.
    return [(title, text) for title, text in sections if text != ""]


def make_chunks(document):
    header = document["header"]
    chunks = []

    sections = split_into_sections(document["body"])
    for number, (section_title, section_text) in enumerate(sections, start=1):
        chunks.append({
            "chunk_id": header["doc_id"] + "#" + str(number),
            "doc_id": header["doc_id"],
            "title": header["title"],
            "section": section_title,
            "text": section_text,
            # Access fields are copied from the validated header into EVERY chunk.
            "clearance": header["clearance"],
            "department": header["department"],
            "allowed_roles": header["allowed_roles"],
        })

    return chunks