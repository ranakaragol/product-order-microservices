FROM python:3.11-slim
WORKDIR /
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
COPY . .
ENV PYTHONPATH=/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]