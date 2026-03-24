FROM python:3.11-slim AS base
WORKDIR /
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
ENV PYTHONPATH=/

FROM base AS test
COPY requirements-dev.txt /requirements-dev.txt
RUN pip install --no-cache-dir -r /requirements-dev.txt
COPY . .
CMD ["pytest", "tests"]

FROM base AS runtime
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
