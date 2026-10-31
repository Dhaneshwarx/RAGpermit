"""Local administrator document operations with persistent stale-index protection."""
import os
import re
from src.config import workspace_path
from src.document_loader import load_document, split_header_and_body, parse_header_lines, validate_header
from src.chunker import make_chunks
from src.ingest import embed_chunks
from src.vector_store import open_store, rebuild_collection, store_chunks
from src.audit import write_audit_entry


def dirty():
    return workspace_path('data/index-dirty').exists()


def document_path(doc_id):
    if not isinstance(doc_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', doc_id):
        raise ValueError('Document ID must use lowercase letters, numbers and hyphens.')
    return workspace_path('data/docs') / (doc_id + '.md')


def inventory():
    result = []
    for path in sorted(workspace_path('data/docs').glob('*.md')):
        try:
            result.append({'header': load_document(path)['header'], 'content': path.read_text(encoding='utf-8-sig')})
        except ValueError:
            result.append({'header': {'doc_id': path.stem, 'title': path.stem}, 'content': path.read_text(encoding='utf-8-sig'), 'invalid': True})
    return {'documents': result, 'needs_indexing': dirty()}


def change(user_id, action, doc_id, content=None):
    path = document_path(doc_id)
    if action == 'save':
        if not isinstance(content, str) or len(content.encode('utf-8')) > 200000:
            raise ValueError('Document must contain at most 200 KB of UTF-8 text.')
        header, body = split_header_and_body(content.lstrip('\ufeff'))
        header = validate_header(parse_header_lines(header))
        if header['doc_id'] != doc_id or not body.strip():
            raise ValueError('Header ID must match the document ID and body must not be empty.')
    elif action != 'delete' or not path.is_file():
        raise ValueError('Document not found or invalid operation.')
    write_audit_entry({'status': 'admin_document_change', 'user_id': user_id, 'action': action, 'doc_id': doc_id})
    marker = workspace_path('data/index-dirty')
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('Rebuild required', encoding='utf-8')
    if action == 'delete':
        path.unlink()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.pending')
        temporary.write_text(content.lstrip('\ufeff'), encoding='utf-8')
        os.replace(temporary, path)


def reindex(user_id):
    chunks = []
    for path in sorted(workspace_path('data/docs').glob('*.md')):
        chunks.extend(make_chunks(load_document(path)))
    vectors = embed_chunks(chunks) if chunks else []
    write_audit_entry({'status': 'admin_reindex_started', 'user_id': user_id})
    marker = workspace_path('data/index-dirty')
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('Rebuild required', encoding='utf-8')
    client = open_store()
    try:
        rebuild_collection(client)
        if chunks:
            store_chunks(client, chunks, vectors)
    finally:
        client.close()
    write_audit_entry({'status': 'admin_reindex_completed', 'user_id': user_id, 'chunks': len(chunks)})
    marker.unlink(missing_ok=True)
    return len(chunks)
