from py2neo import Graph
from core.settings import settings

URI = settings.uri
USERNAME = settings.db_username
PASSWORD = settings.db_password

graph = Graph(URI, auth=(USERNAME, PASSWORD))

# graph.run("CREATE INDEX user_index IF NOT EXISTS FOR (u:User) ON (u.username)")
# graph.run("CREATE INDEX group_index IF NOT EXISTS FOR (g:Group) ON (g.title)")
