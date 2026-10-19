FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY knowledge ./knowledge
RUN pip install --no-cache-dir . && useradd --create-home knowledge
USER knowledge
CMD ["uvicorn", "knowledge.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
