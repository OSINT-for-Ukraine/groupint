from py2neo import Graph
from core.settings import settings
import os

# URI = settings.uri
# USERNAME = settings.db_username
# PASSWORD = settings.db_password

URI = os.environ.get("NEO4J_URI")
USERNAME = os.environ.get("NEO4J_USERNAME")
PASSWORD = os.environ.get("NEO4J_PASSWORD")

graph = Graph(URI, auth=(USERNAME, PASSWORD))

# graph.run("CREATE INDEX user_index IF NOT EXISTS FOR (u:User) ON (u.username)")
# graph.run("CREATE INDEX group_index IF NOT EXISTS FOR (g:Group) ON (g.title)")
