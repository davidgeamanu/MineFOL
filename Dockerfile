# Debian-based, not Alpine: bin/prover9 and bin/mace4 need glibc 2.34 or newer
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bin/ bin/
COPY Python/ Python/
COPY build/games/ build/games/

RUN useradd --create-home minefol
USER minefol

EXPOSE 8000

# 1 worker: games live in memory, a second worker would have its own copy
CMD ["gunicorn", "--chdir", "Python/web", "--workers", "1", "--threads", "4", \
     "--bind", "0.0.0.0:8000", "--access-logfile", "-", "app:app"]
