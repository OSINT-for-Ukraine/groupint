FROM python:3.11
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock README.md ./
COPY core ./core
COPY db ./db
COPY models.py main.py ./
RUN python3.11 -m pip install --no-cache-dir .

COPY . .

RUN set -ex \
    && addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 --gid 1001 --home /home/appuser appuser \
    && mkdir -p /home/appuser/.streamlit /home/appuser/.groupint/sessions \
    && chown -R appuser:appgroup /home/appuser /app

ENV HOME=/home/appuser

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health
RUN chmod +x /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["streamlit", "run", "interface.py", "--server.port=8501", "--server.address=0.0.0.0"]
