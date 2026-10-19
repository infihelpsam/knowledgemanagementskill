import hashlib
import re
from typing import Protocol
import numpy as np


def tokens(text):
    return re.findall(r'\w+', text.lower())


class Embedder(Protocol):
    identity: str
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class Reranker(Protocol):
    def rank(self, query: str, hits: list[dict]) -> list[dict]: ...


class Answerer(Protocol):
    def answer(self, query: str, authorized_hits: list[dict]) -> dict: ...


class HashEmbedder:
    """Offline feature hashing baseline; not a learned semantic model."""
    def __init__(self, dimensions):
        self.dimensions = dimensions
        self.identity = f'hash-v1:{dimensions}'

    def embed(self, texts):
        result = []
        for text in texts:
            vector = np.zeros(self.dimensions)
            for token in tokens(text):
                digest = hashlib.sha256(token.encode()).digest()
                vector[int.from_bytes(digest[:4], 'big') % self.dimensions] += 1 if digest[4] & 1 else -1
            length = np.linalg.norm(vector)
            result.append((vector / length if length else vector).tolist())
        return result


class SentenceEmbedder:
    def __init__(self, model, dimensions):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model, trust_remote_code=False)
        self.dimensions = dimensions
        if self.model.get_sentence_embedding_dimension() != dimensions:
            raise ValueError('Model dimensions differ from configured database dimensions')
        self.identity = f'sentence-transformers:{model}:{dimensions}'

    def embed(self, texts):
        return self.model.encode(texts, normalize_embeddings=True).tolist()


class OpenAIEmbedder:
    def __init__(self, config):
        self.config = config
        self.identity = f'openai:{config.openai_embedding_model}:{config.embedding_dimensions}'

    def embed(self, texts):
        import httpx
        with httpx.Client(timeout=30, trust_env=False) as client:
            response = client.post('https://api.openai.com/v1/embeddings', headers={'Authorization': f'Bearer {self.config.openai_api_key}'}, json={'model': self.config.openai_embedding_model, 'input': texts, 'dimensions': self.config.embedding_dimensions})
            response.raise_for_status()
            return [r['embedding'] for r in sorted(response.json()['data'], key=lambda r: r['index'])]


def provider(config):
    if config.embedding_provider == 'hash':
        return HashEmbedder(config.embedding_dimensions)
    if config.embedding_provider == 'sentence-transformers':
        return SentenceEmbedder(config.embedding_model, config.embedding_dimensions)
    return OpenAIEmbedder(config)


class OverlapReranker:
    def rank(self, query, hits):
        wanted = set(tokens(query))
        return sorted(hits, key=lambda h: len(wanted & set(tokens(h['text']))), reverse=True)


def grounded_answer(query, hits, minimum=0.2):
    """Extractive RAG: documents can only become quoted data, never instructions."""
    wanted = set(tokens(query)) - {'a', 'an', 'the', 'is', 'are', 'what', 'how', 'do', 'i'}
    evidence = []
    for hit in hits:
        overlap = len(wanted & set(tokens(hit['text']))) / max(1, len(wanted))
        if wanted and overlap >= minimum:
            evidence.append(hit)
    if not evidence:
        return {'answer': 'Insufficient evidence.', 'abstained': True, 'citations': []}
    evidence = evidence[:3]
    return {'answer': '\n\n'.join(f'[{i}] {h["text"]}' for i, h in enumerate(evidence, 1)), 'abstained': False,
            'citations': [{'label': i, 'document_id': str(h['document_id']), 'version': h['version'], 'chunk': h['ordinal'], 'source': h['source'], 'start': h['start_char'], 'end': h['end_char'], 'quote': h['text']} for i, h in enumerate(evidence, 1)]}
