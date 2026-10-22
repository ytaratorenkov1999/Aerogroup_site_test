FROM python:3.14-slim

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY support_ag_ife_com/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY support_ag_ife_com/ /app/

RUN mkdir -p /app/staticfiles

EXPOSE 8000