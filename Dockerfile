FROM python:3.11
WORKDIR /app 
COPY . .

RUN curl -sSL https://install.python-poetry.org | python3 -
RUN set -ex \
    # Create a non-root user with a writable home (Streamlit writes ~/.streamlit)
    && addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 --gid 1001 --home /home/appuser appuser \
    && mkdir -p /home/appuser/.streamlit \
    && chown -R appuser:appgroup /home/appuser \
    && python3.11 -m pip install .

ENV HOME=/home/appuser

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health
RUN chmod +x /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["streamlit", "run", "interface.py", "--server.port=8501", "--server.address=0.0.0.0"]
