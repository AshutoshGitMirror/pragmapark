FROM python:3.12-slim

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .

RUN mkdir -p /var/lib/pragma && chown app:app /var/lib/pragma

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
  CMD python -c "import urllib.request; exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health').status == 200 else 1)"

ENV BLOCKCHAIN_PATH=/var/lib/pragma/blockchain.json

CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
