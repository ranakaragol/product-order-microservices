FROM python:3.11-slim
WORKDIR /
COPY . .
RUN pip install --no-cache-dir fastapi uvicorn motor python-jose[cryptography] bcrypt
ENV PYTHONPATH=/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]