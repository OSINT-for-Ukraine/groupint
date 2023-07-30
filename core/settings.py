from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    uri: str = "bolt://localhost:7687"
    db_username: str = "neo4j"
    db_password: str = "difficulties-pushup-gaps"


settings = Settings()
