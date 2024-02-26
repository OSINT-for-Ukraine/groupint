FROM python:3.11
WORKDIR /app 
COPY . .

RUN curl -sSL https://install.python-poetry.org | python3 -

RUN python3.11 -m pip install .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit","run","interface.py","--server.port=8501", "--server.address=0.0.0.0"]