"""Command-line interface for Market_Sentry."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from marketsentry.config import config
from marketsentry.database import (
    get_table_count,
    init_db,
    table_exists,
)
from marketsentry.logging_config import logger

app = typer.Typer(
    name="marketsentry",
    help="Market_Sentry: Buyer-side real-estate market observation and watchlist system",
)
console = Console()


@app.command()
def init_database(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Initialize the Market_Sentry database."""
    try:
        db_path = database_path or config.database_path
        console.print(f"[bold blue]Initializing database at:[/bold blue] {db_path}")

        # Ensure directories exist
        config.ensure_directories()

        # Initialize database
        init_db(db_path)

        # Verify tables were created
        tables = [
            "candidate_review_queue",
            "watched_properties",
            "property_observation_snapshots",
            "listing_events",
            "source_pages",
            "user_review_actions",
        ]

        all_exist = all(table_exists(table, db_path) for table in tables)

        if all_exist:
            console.print("[bold green]SUCCESS:[/bold green] Database initialized successfully")
            console.print(f"\n[dim]Tables created:[/dim]")
            for table in tables:
                console.print(f"  - {table}")
        else:
            console.print("[bold red]ERROR:[/bold red] Database initialization incomplete")
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Database initialization error: {e}")
        raise typer.Exit(code=1)


@app.command()
def status(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Show database status and record counts."""
    try:
        db_path = database_path or config.database_path

        if not Path(db_path).exists():
            console.print(
                f"[bold yellow]Database not found:[/bold yellow] {db_path}\n"
                f"[dim]Run 'marketsentry init-database' to create it.[/dim]"
            )
            raise typer.Exit(code=0)

        # Create status table
        table = Table(title="Market_Sentry Database Status")
        table.add_column("Table", style="cyan")
        table.add_column("Records", justify="right", style="magenta")

        tables = [
            ("Candidate Review Queue", "candidate_review_queue"),
            ("Watched Properties", "watched_properties"),
            ("Observation Snapshots", "property_observation_snapshots"),
            ("Listing Events", "listing_events"),
            ("Source Pages", "source_pages"),
            ("User Review Actions", "user_review_actions"),
        ]

        for display_name, table_name in tables:
            count = get_table_count(table_name, db_path)
            table.add_row(display_name, str(count))

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Status check error: {e}")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show Market_Sentry version."""
    from marketsentry import __version__

    console.print(f"Market_Sentry version [bold cyan]{__version__}[/bold cyan]")


@app.command()
def config_show() -> None:
    """Show current configuration."""
    console.print("[bold blue]Current Configuration:[/bold blue]\n")

    config_items = [
        ("Database Path", config.database_path),
        ("Data Raw Directory", config.data_raw_dir),
        ("Data Processed Directory", config.data_processed_dir),
        ("Data Exports Directory", config.data_exports_dir),
        ("Data Imports Directory", config.data_imports_dir),
        ("Log File", config.log_file),
        ("Log Level", config.log_level),
        ("Quiet Score Minimum", str(config.quiet_score_minimum)),
        ("Quiet Score Target", str(config.quiet_score_target)),
        ("Vibrancy Score Target Max", str(config.vibrancy_score_target_max)),
        ("Effective DOM Lookback Days", str(config.effective_dom_lookback_days)),
    ]

    for name, value in config_items:
        console.print(f"[cyan]{name}:[/cyan] {value}")


if __name__ == "__main__":
    app()
