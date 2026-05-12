"""
Fallback Postgres URL when the DATABASE_URL environment variable is not set.

Railway / local: if DATABASE_URL is unset, this Neon URL is used. When set,
DATABASE_URL always wins. `channel_binding` is omitted (see app.config.normalize_database_url).
"""

DEFAULT_DATABASE_URL = (
    "postgresql://neondb_owner:npg_o0AQ3MrwCJOl@ep-bold-darkness-aq3a4qkq-pooler.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require"
)
