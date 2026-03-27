FROM python:3.14-slim

WORKDIR /app

COPY postgres/ .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./shared ./shared

CMD ["python", "collector.py"]
