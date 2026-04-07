"""Database migration — no-op for Supabase (schema managed via Supabase migrations)."""
from supabase import Client


def db_init_and_migrate(sb: Client) -> None:
    """Schema is managed via Supabase migrations. Nothing to do at runtime."""
    pass
