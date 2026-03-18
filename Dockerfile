FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app

COPY gold_trading_backend/ gold_trading_backend/

EXPOSE 8000

CMD ["sh", "-c", "uvicorn gold_trading_backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
