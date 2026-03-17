FROM python:3.11-slim
WORKDIR /
COPY . .
ENV PYTHONPATH=/
RUN pip install --no-cache-dir fastapi uvicorn httpx python-jose[cryptography]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]