version: '3.8'
services:
  neo4j:
    container_name: ${APP_NAME}-neo4j
    image: neo4j
    ports:
      - "7474:7474"
      - "7473:7473"
      - "7687:7687"
    volumes:
      - $HOME/neo4j/${NEO4J_USER}/data:/data
      - $HOME/neo4j/${NEO4J_USER}/logs:/logs
      - $HOME/neo4j/${NEO4J_USER}/import:/var/lib/neo4j/import
      - $HOME/neo4j/${NEO4J_USER}/plugins:/plugins
    environment:
      - NEO4J_AUTH=${NEO4J_USER}/${NEO4J_PASSWORD}
      - NEO4J_apoc_export_file_enabled=true
      - NEO4J_apoc_import_file_enabled=true
      - NEO4J_apoc_import_file_use__neo4j__config=true
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*,gds.*
      - NEO4JLABS_PLUGINS='["apoc", "graph-data-science"]'
    restart: always
  streamlit:
    container_name: groupint-streamlit
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - HOST=localhost
      - NEO4J_URI=bolt://${APP_NAME}-neo4j:7687
      - NEO4J_USERNAME=${NEO4J_USER}
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - APP_NAME=${APP_NAME}
    restart: always
    ports:
      - "8501:8501"
    volumes:
      - .:/app
    depends_on:
      - neo4j