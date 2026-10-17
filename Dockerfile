FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instala o Chromium e todas as bibliotecas do sistema Linux
RUN playwright install --with-deps chromium

COPY . .

CMD ["python", "-u", "main.py"]