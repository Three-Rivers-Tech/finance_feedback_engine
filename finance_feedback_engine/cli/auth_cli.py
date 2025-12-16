"""API key management CLI commands."""

import os
import sys
from pathlib import Path
from typing import Optional

import click
from tabulate import tabulate

from ..auth import AuthManager


@click.group()
def auth_group():
    """Manage API keys and authentication settings."""
    pass


def _get_auth_manager() -> AuthManager:
    """Initialize and return auth manager."""
    return AuthManager()


@auth_group.command("add-key")
@click.option(
    "--name",
    required=True,
    prompt="Key identifier (e.g., 'my-service')",
    help="Unique name for the API key",
)
@click.option(
    "--key",
    required=False,
    prompt="API Key (will be hidden)",
    hide_input=True,
    help="The actual API key (input will be hidden)",
)
@click.option("--description", default="", help="Optional description for this key")
def add_api_key(name: str, key: str, description: str):
    """Add a new API key to the secure database.

    Example:
        python main.py auth add-key --name my-service --description "My trading service"
    """
    if not key:
        click.secho("❌ API key cannot be empty", fg="red")
        sys.exit(1)

    auth_manager = _get_auth_manager()

    try:
        success = auth_manager.add_api_key(name, key, description)
        if success:
            click.secho(
                f"✅ API key '{name}' added successfully to database", fg="green"
            )
            click.secho(
                "💡 Add to config/config.local.yaml for fallback (optional):", fg="blue"
            )
            click.echo(f"  api_keys:")
            click.echo(f"    {name}: '{key}'")
        else:
            click.secho(f"⚠️  API key '{name}' already exists in database", fg="yellow")
            sys.exit(1)

    except Exception as e:
        click.secho(f"❌ Error adding API key: {e}", fg="red")
        sys.exit(1)


@auth_group.command("test-key")
@click.option(
    "--key",
    required=False,
    prompt="API Key to test",
    hide_input=True,
    help="The API key to validate",
)
@click.option("--ip", default="127.0.0.1", help="Client IP for logging")
def test_api_key(key: str, ip: str):
    """Test an API key without making API requests.

    Example:
        python main.py auth test-key
    """
    if not key:
        click.secho("❌ API key cannot be empty", fg="red")
        sys.exit(1)

    auth_manager = _get_auth_manager()

    try:
        is_valid, key_name, metadata = auth_manager.validate_api_key(
            api_key=key, ip_address=ip, user_agent="CLI-Test"
        )

        if is_valid:
            click.secho(f"✅ API key is valid (name: '{key_name}')", fg="green")
            click.echo("\n📊 Rate limit info:")
            click.echo(
                f"  Remaining requests: {metadata.get('remaining_requests', 'N/A')}"
            )
            click.echo(f"  Window: {metadata.get('window_seconds', 'N/A')}s")
            click.echo(f"  Reset at: {metadata.get('reset_time', 'N/A')}")
        else:
            click.secho("❌ API key is invalid or inactive", fg="red")
            sys.exit(1)

    except ValueError as e:
        click.secho(f"❌ Rate limit exceeded: {e}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"❌ Error validating API key: {e}", fg="red")
        sys.exit(1)


@auth_group.command("list-keys")
def list_api_keys():
    """List all stored API keys (metadata only, not the actual keys).

    Example:
        python main.py auth list-keys
    """
    import sqlite3

    auth_manager = _get_auth_manager()

    try:
        with sqlite3.connect(auth_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    name,
                    key_hash,
                    created_at,
                    last_used,
                    is_active,
                    description
                FROM api_keys
                ORDER BY created_at DESC
            """
            )

            rows = cursor.fetchall()

            if not rows:
                click.secho("ℹ️  No API keys found", fg="cyan")
                return

            # Prepare data for table
            table_data = []
            for row in rows:
                table_data.append(
                    [
                        row["name"],
                        row["key_hash"][:16] + "...",  # Truncate hash
                        row["created_at"],
                        row["last_used"] or "Never",
                        "✅ Active" if row["is_active"] else "❌ Disabled",
                        row["description"] or "-",
                    ]
                )

            click.echo("\n📋 Stored API Keys:\n")
            click.echo(
                tabulate(
                    table_data,
                    headers=[
                        "Name",
                        "Key Hash",
                        "Created",
                        "Last Used",
                        "Status",
                        "Description",
                    ],
                    tablefmt="grid",
                )
            )

    except Exception as e:
        click.secho(f"❌ Error listing API keys: {e}", fg="red")
        sys.exit(1)


@auth_group.command("disable-key")
@click.option(
    "--name",
    required=True,
    prompt="Key name to disable",
    help="The key identifier to disable",
)
def disable_api_key(name: str):
    """Disable an API key (revoke access without deletion).

    Example:
        python main.py auth disable-key --name old-service
    """
    import sqlite3

    auth_manager = _get_auth_manager()

    try:
        with sqlite3.connect(auth_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE api_keys SET is_active = 0 WHERE name = ?
            """,
                (name,),
            )
            conn.commit()

            if cursor.rowcount > 0:
                click.secho(f"✅ API key '{name}' has been disabled", fg="green")
            else:
                click.secho(f"⚠️  API key '{name}' not found", fg="yellow")
                sys.exit(1)

    except Exception as e:
        click.secho(f"❌ Error disabling API key: {e}", fg="red")
        sys.exit(1)


@auth_group.command("show-audit-log")
@click.option("--limit", default=50, help="Number of recent entries to show")
@click.option("--hours", default=24, help="Look back this many hours")
@click.option("--failures-only", is_flag=True, help="Show only failed attempts")
def show_audit_log(limit: int, hours: int, failures_only: bool):
    """Show authentication audit log.

    Example:
        python main.py auth show-audit-log --hours 2
    """
    import sqlite3

    auth_manager = _get_auth_manager()

    try:
        with sqlite3.connect(auth_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            from datetime import datetime, timedelta

            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            where_clause = "WHERE timestamp > ?"
            params = [cutoff_time.isoformat()]

            if failures_only:
                where_clause += " AND success = 0"

            # Build the query safely by using only parameterized queries
            base_query = """
                SELECT
                    timestamp,
                    api_key_hash,
                    success,
                    ip_address,
                    user_agent,
                    error_reason
                FROM auth_audit_log
                WHERE timestamp > ?
            """

            # Add failures-only condition if needed
            if failures_only:
                base_query += " AND success = 0"

            base_query += " ORDER BY timestamp DESC LIMIT ?"

            cursor.execute(base_query, params + [limit])

            rows = cursor.fetchall()

            if not rows:
                click.secho(
                    f"ℹ️  No audit log entries found in last {hours} hours", fg="cyan"
                )
                return

            # Prepare data for table
            table_data = []
            for row in rows:
                status = "✅ Success" if row["success"] else "❌ Failed"
                table_data.append(
                    [
                        row["timestamp"],
                        row["api_key_hash"][:16] + "...",
                        status,
                        row["ip_address"] or "-",
                        row["error_reason"] or "-",
                    ]
                )

            click.echo(f"\n📋 Authentication Audit Log (last {hours} hours):\n")
            click.echo(
                tabulate(
                    table_data,
                    headers=["Timestamp", "Key Hash", "Status", "IP Address", "Error"],
                    tablefmt="grid",
                )
            )

            # Show statistics - safe query without string formatting
            base_stats_query = """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
                FROM auth_audit_log
                WHERE timestamp > ?
            """

            # Add failures-only condition if needed
            if failures_only:
                base_stats_query += " AND success = 0"

            cursor.execute(base_stats_query, params)

            stats = cursor.fetchone()
            click.echo("\n📊 Statistics:")
            click.echo(f"  Total attempts: {stats['total']}")
            click.echo(f"  Successful: {stats['successful']}")
            click.echo(f"  Failed: {stats['failed']}")
            if stats["total"] > 0:
                success_rate = (stats["successful"] / stats["total"]) * 100
                click.echo(f"  Success rate: {success_rate:.1f}%")

    except Exception as e:
        click.secho(f"❌ Error reading audit log: {e}", fg="red")
        sys.exit(1)


@auth_group.command("stats")
def auth_stats():
    """Show authentication statistics.

    Example:
        python main.py auth stats
    """
    auth_manager = _get_auth_manager()

    try:
        stats = auth_manager.get_key_stats(hours_back=24)

        click.echo("\n📊 Authentication Statistics (last 24 hours):\n")
        click.echo(f"  Total attempts:  {stats.get('total', 0)}")
        click.echo(f"  Successful:      {stats.get('successful', 0)}")
        click.echo(f"  Failed:          {stats.get('failed', 0)}")

        total = stats.get("total", 0)
        if total > 0:
            success_rate = (stats.get("successful", 0) / total) * 100
            click.echo(f"  Success rate:    {success_rate:.1f}%")

        click.echo(
            "\n💡 Tip: Run 'python main.py auth show-audit-log' for detailed logs"
        )

    except Exception as e:
        click.secho(f"❌ Error getting statistics: {e}", fg="red")
        sys.exit(1)
