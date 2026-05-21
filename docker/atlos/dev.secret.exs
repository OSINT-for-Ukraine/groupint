import Config

config :platform, Platform.Repo,
  hostname: "atlos-postgres",
  username: "atlos",
  password: "atlos",
  database: "atlos",
  port: 5432

config :platform, PlatformWeb.Endpoint,
  http: [ip: {0, 0, 0, 0}, port: 4000]
