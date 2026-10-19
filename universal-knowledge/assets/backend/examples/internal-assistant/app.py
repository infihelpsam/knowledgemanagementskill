"""Owner ingests; a separate token for employee-1 can retrieve the shared policy."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from integrations.client import KnowledgeClient

client = KnowledgeClient(os.environ.get('KNOWLEDGE_URL', 'http://localhost:8000'), os.environ['KNOWLEDGE_TOKEN'])
try:
    print(client.upload(str(Path(__file__).with_name('handbook.md')), ['user:employee-1'], {'collection': 'internal'}))
    print('Poll the returned job_id until complete, then use employee-1 token to ask about annual leave.')
finally:
    client.close()
