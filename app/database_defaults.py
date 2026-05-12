"""
Fallback Postgres URL when the DATABASE_URL environment variable is not set.

On Railway, set DATABASE_URL to Neon’s full string (often includes
`channel_binding=require`). The app strips `channel_binding` before connect
(see app.config.normalize_database_url) so asyncpg/Neon pooler stay reliable.
"""

DEFAULT_DATABASE_URL = (
    "postgresql://neondb_owner:npg_o0AQ3MrwCJOl@ep-bold-darkness-aq3a4qkq-pooler.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)
