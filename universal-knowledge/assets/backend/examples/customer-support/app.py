"""Run from backend root: python examples/customer-support/app.py"""
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from integrations.client import KnowledgeClient

client = KnowledgeClient(os.environ.get('KNOWLEDGE_URL', 'http://localhost:8000'), os.environ['KNOWLEDGE_TOKEN'])
try:
    job = client.upload(str(Path(__file__).with_name('faq.md')), ['group:support'], {'collection': 'support'})
    for _ in range(60):
        status = client.status(job['job_id'])['status']
        if status == 'complete': break
        if status in {'failed', 'superseded'}: raise RuntimeError(status)
        time.sleep(1)
    else: raise TimeoutError('Ingestion did not finish')
    print(client.answer('How long does the warranty last?', {'collection': 'support'}))
finally:
    client.close()
