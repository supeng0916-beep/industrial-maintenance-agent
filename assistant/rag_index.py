"""Local cosine Chroma indexes. A completed index.json is the publication marker."""
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import time

SCHEMA = 'maintenance-rag-v1'
COLLECTION = 'maintenance_documents'
DISTANCE = 'cosine distance = 1 - cosine similarity; smaller is closer, not confidence or answerability'
FILTERS = {'document_id', 'language', 'publisher', 'product_model', 'device_id', 'teaching_only', 'source_document_id'}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


@contextmanager
def _client(path):
    # Set before importing Chroma/OpenTelemetry; never auto-download an embedding model.
    os.environ['ANONYMIZED_TELEMETRY'] = 'False'
    os.environ['OTEL_SDK_DISABLED'] = 'true'
    import chromadb
    from chromadb.config import Settings
    client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
    try:
        yield client
    finally:
        if hasattr(client, 'close'):
            client.close()
        else:
            # Pinned Chroma releases without public close: stop only this owned path.
            client._system.stop()
            from chromadb.api.shared_system_client import SharedSystemClient
            SharedSystemClient._identifier_to_system.pop(client._identifier, None)


def _vectors(values, count, dimension):
    if len(values) != count or any(len(row) != dimension for row in values):
        raise ValueError('embedding dimension/count mismatch')
    if any(not all(math.isfinite(float(x)) for x in row) or sum(float(x)**2 for x in row) == 0 for row in values):
        raise ValueError('embedding values must be finite and nonzero')


def create_index(output, chunks, embedder, corpus):
    """Build a wholly new local index. Failed builds remove only their own directory."""
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'index already exists; choose a new directory: {output}')
    if not chunks or len({c['chunk_id'] for c in chunks}) != len(chunks):
        raise ValueError('index requires nonempty chunks with unique IDs')
    started = time.monotonic()
    # Inference failure must not publish any index.
    vectors = embedder.embed([c['embedding_text'] for c in chunks])
    _vectors(vectors, len(chunks), embedder.signature['dimension'])
    signature_hash, chunks_hash = _digest(embedder.signature), _digest(chunks)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    try:
        with _client(output/'chroma') as client:
            collection = client.create_collection(
                COLLECTION, embedding_function=None,
                configuration={'hnsw': {'space': 'cosine'}},
                metadata={'model_signature_sha256':signature_hash,'chunks_sha256':chunks_hash,'schema':SCHEMA})
            for start in range(0, len(chunks), 128):
                batch = chunks[start:start+128]
                collection.add(ids=[c['chunk_id'] for c in batch],
                               embeddings=vectors[start:start+128],
                               documents=[c['original_text'] for c in batch],
                               metadatas=[{'document_id':c['document_id'],'version':c['version'],'section':c['section']} for c in batch])
            if collection.count() != len(chunks):
                raise ValueError('index count validation failed')
        # Reopen the real persisted store before publishing the success marker.
        with _client(output/'chroma') as client:
            if client.get_collection(COLLECTION, embedding_function=None).count() != len(chunks):
                raise ValueError('persisted index count validation failed')
        (output/'chunks.json').write_text(_json(chunks)+'\n', encoding='utf-8')
        config = dict(schema=SCHEMA, model_signature=embedder.signature,
                      model_signature_sha256=signature_hash, chunks_sha256=chunks_hash,
                      chunk_count=len(chunks), document_count=len({c['document_id'] for c in chunks}),
                      distance='cosine', chromadb_version=importlib.metadata.version('chromadb'),
                      storage_files=sorted(str(p.relative_to(output)) for p in (output/'chroma').rglob('*') if p.is_file() and not p.name.endswith(('-wal','-shm'))),
                      corpus=corpus, build_seconds=time.monotonic()-started,
                      limitations=['Candidates are evidence to inspect, not diagnosis or proof of applicability.'])
        (output/'index.json').write_text(_json(config)+'\n', encoding='utf-8')
    except BaseException:
        shutil.rmtree(output)
        raise
    return config


def read_index(index):
    index = Path(index)
    try:
        config = json.loads((index/'index.json').read_text(encoding='utf-8'))
        chunks = json.loads((index/'chunks.json').read_text(encoding='utf-8'))
        if not (index/'chroma'/'chroma.sqlite3').is_file():
            raise ValueError('missing Chroma database')
        for storage_file in config['storage_files']:
            relative = Path(storage_file)
            if relative.is_absolute() or '..' in relative.parts or not (index/relative).is_file():
                raise ValueError(f'missing or invalid storage file: {storage_file}')
        if config['schema'] != SCHEMA or config['distance'] != 'cosine':
            raise ValueError('index configuration mismatch')
        if _digest(chunks) != config['chunks_sha256'] or _digest(config['model_signature']) != config['model_signature_sha256']:
            raise ValueError('index integrity mismatch')
        if not chunks or len(chunks) != config['chunk_count'] or len({c['chunk_id'] for c in chunks}) != len(chunks):
            raise ValueError('empty or inconsistent index')
        return config, chunks
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f'index unavailable or invalid: {exc}') from exc


def _eligible(chunks, filters):
    if not isinstance(filters, dict) or set(filters) - FILTERS:
        raise ValueError('unknown filter field')
    def value(chunk, key):
        if key == 'device_id': return chunk['metadata'].get('device_ids', [])
        if key == 'document_id': return [chunk['document_id']]
        v = chunk['metadata'].get(key)
        return [] if v is None else [v]
    for key, requested in filters.items():
        if key == 'teaching_only': valid_type = type(requested) is bool
        else: valid_type = isinstance(requested, str) and bool(requested.strip())
        if not valid_type or not any(requested in value(c, key) for c in chunks):
            raise ValueError(f'unknown filter value: {key}={requested!r}')
    return [c for c in chunks if all(requested in value(c,key) for key,requested in filters.items())]


def search_index(index, query, embedder, *, top_k=5, filters=None):
    if type(top_k) is not int or not 1 <= top_k <= 10:
        raise ValueError('top_k must be an integer from 1 to 10')
    if not isinstance(query, str) or not query.strip():
        raise ValueError('query must be nonempty text')
    config, chunks = read_index(index)
    if config['model_signature'] != embedder.signature:
        raise ValueError('model signature mismatch; rebuild a separate index')
    eligible = _eligible(chunks, {} if filters is None else filters)
    answer = dict(ok=True, query=query, top_k=top_k, model_signature=embedder.signature,
                  distance_semantics=DISTANCE, candidates=[],
                  limitations=['Candidates do not establish diagnosis, correctness, or answerability.',
                               'Empty device_ids or unknown product_model does not mean universally applicable.'])
    # Check the persisted collection even if a valid filter intersection is empty.
    with _client(Path(index).absolute()/'chroma') as client:
        collection = client.get_collection(COLLECTION, embedding_function=None)
        metadata = collection.metadata or {}
        if (metadata.get('model_signature_sha256') != config['model_signature_sha256'] or
            metadata.get('chunks_sha256') != config['chunks_sha256'] or collection.count() != len(chunks)):
            raise ValueError('persisted collection signature/integrity mismatch')
        if collection.configuration['hnsw']['space'] != 'cosine':
            raise ValueError('persisted collection distance mismatch')
        if not eligible: return answer
        vector = embedder.embed([embedder.format_query(query)])
        _vectors(vector, 1, embedder.signature['dimension'])
        where = {'document_id': {'$in': sorted({c['document_id'] for c in eligible})}}
        rows = collection.query(query_embeddings=vector, n_results=min(top_k,len(eligible)),
                                where=where, include=['distances'])
        by_id = {c['chunk_id']:c for c in eligible}
        for rank, (key, distance) in enumerate(zip(rows['ids'][0], rows['distances'][0]),1):
            if key not in by_id or not math.isfinite(distance):
                raise ValueError('query returned inconsistent candidate')
            c = by_id[key]
            answer['candidates'].append(dict(c, rank=rank, distance=float(distance),
                source_pages=c.get('source_pages', c['metadata'].get('source_pages',[])),
                source_url=c['metadata'].get('source_url')))
    return answer
