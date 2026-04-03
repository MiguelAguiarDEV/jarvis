# JARVIS Docker Compose — 1Password env template
# Usage: op run --env-file=.env.tpl -- docker compose up -d

# Postgres
POSTGRES_USER=op://Desarrollo/jarvis-postgres/username
POSTGRES_PASSWORD=op://Desarrollo/jarvis-postgres/password

# Engram Cloud
ENGRAM_JWT_SECRET=op://Desarrollo/jarvis-engram-cloud/jwt_secret
ENGRAM_DATABASE_URL=op://Desarrollo/jarvis-engram-cloud/database_url
ENGRAM_CLOUD_API_KEY=op://Desarrollo/jarvis-engram-cloud/cloud_api_key

# Discord Bot
DISCORD_TOKEN=op://Desarrollo/jarvis-discord-bot/password
DISCORD_APP_ID=op://Desarrollo/jarvis-discord-bot/app_id
DISCORD_GUILD_ID=op://Desarrollo/jarvis-discord-bot/server_id
DISCORD_USER_ID=op://Desarrollo/jarvis-discord-bot/user_id

# Opencode Server
OPENCODE_SERVER_PASSWORD=op://Desarrollo/jarvis-opencode-server/password

# Engram Cloud Auth
ENGRAM_USER=op://Desarrollo/jarvis-engram-cloud-auth/username
ENGRAM_PASS=op://Desarrollo/jarvis-engram-cloud-auth/engram_password

# Dashboard
ENGRAM_API_KEY=op://Desarrollo/jarvis-dashboard/api_key

# PROMETHEUS — Claude API (setup-token, long-lived)
CLAUDE_API_TOKEN=op://Desarrollo/jarvis-claude-setup-token/password
