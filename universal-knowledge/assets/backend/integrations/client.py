"""Server-side Python integration; never embed service tokens in browser code."""
import base64
from pathlib import Path
import httpx


class KnowledgeClient:
    def __init__(self, base_url: str, token: str):
        self.http = httpx.Client(base_url=base_url, headers={'Authorization': f'Bearer {token}'}, timeout=30)

    def upload(self, path: str, readers=None, metadata=None):
        file = Path(path)
        if file.stat().st_size > 10_000_000:
            raise ValueError('File exceeds default upload limit')
        response = self.http.post('/v1/documents', json={'filename': file.name, 'content_base64': base64.b64encode(file.read_bytes()).decode(), 'readers': readers or [], 'metadata': metadata or {}})
        response.raise_for_status()
        return response.json()

    def answer(self, question: str, filters=None):
        response = self.http.post('/v1/answer', json={'query': question, 'filters': filters or {}})
        response.raise_for_status()
        return response.json()

    def status(self, job_id: str):
        response = self.http.get(f'/v1/jobs/{job_id}')
        response.raise_for_status()
        return response.json()

    def close(self):
        self.http.close()
