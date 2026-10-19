/** Server-side only. Pass a token bound to the authenticated user's tenant/identity. */
export interface Citation {
  label: number; document_id: string; version: number; chunk: number;
  source: string; start: number; end: number; quote: string;
}
export interface Answer { answer: string; abstained: boolean; citations: Citation[] }
export class KnowledgeClient {
  constructor(private baseUrl: string, private token: string) {}
  private async request<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { Authorization: `Bearer ${this.token}`, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(30_000),
    });
    if (!response.ok) throw new Error(`Knowledge API status ${response.status}`);
    return response.json() as Promise<T>;
  }
  answer(query: string, filters: Record<string, unknown> = {}): Promise<Answer> {
    return this.request('/v1/answer', { query, filters });
  }
  upload(filename: string, contentBase64: string, readers: string[] = []) {
    return this.request<{document_id: string; job_id?: string}>('/v1/documents', {
      filename, content_base64: contentBase64, readers,
    });
  }
  status(jobId: string) { return this.request(`/v1/jobs/${encodeURIComponent(jobId)}`); }
}
