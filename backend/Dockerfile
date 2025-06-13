FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    netcat-traditional \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/recipes/management/commands

COPY . .

RUN touch /app/recipes/management/__init__.py
RUN touch /app/recipes/management/commands/__init__.py

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]