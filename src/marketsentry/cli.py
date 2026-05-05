"""Command-line interface for Market_Sentry."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from marketsentry.config import config
from marketsentry.database import (
    get_active_watched_properties,
    get_all_candidates,
    get_table_count,
    init_db,
    table_exists,
)
from marketsentry.logging_config import logger
from marketsentry.review_export import export_candidates_from_db
from marketsentry.review_import import process_review_decisions
from marketsentry.sample_data import seed_sample_candidates
from marketsentry.redfin_url_import import import_redfin_urls_from_csv
from marketsentry.redfin_fixture_parser import parse_redfin_fixtures_from_directory

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


@app.command(name="seed-sample-candidates")
def seed_sample_candidates_cmd(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Seed the database with sample candidates for testing."""
    try:
        db_path = database_path or config.database_path
        console.print("[bold blue]Seeding sample candidates...[/bold blue]")

        count = seed_sample_candidates(db_path)

        console.print(f"[bold green]SUCCESS:[/bold green] Seeded {count} sample candidates")
        console.print("\n[dim]Run 'marketsentry export-review' to export them for review[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Sample data seeding error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_review(
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output CSV file path"
    ),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Export candidate review queue to CSV."""
    try:
        db_path = database_path or config.database_path
        console.print("[bold blue]Exporting candidate review queue...[/bold blue]")

        output_path = export_candidates_from_db(output_file, db_path)

        console.print(f"[bold green]SUCCESS:[/bold green] Exported to {output_path}")
        console.print(
            "\n[dim]Edit the CSV file and set user_decision to: save, reject, maybe, or hold_for_more_data[/dim]"
        )
        console.print("[dim]Then run 'marketsentry import-review --file <path>' to process decisions[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export review error: {e}")
        raise typer.Exit(code=1)


@app.command()
def import_review(
    file: str = typer.Option(..., "--file", "-f", help="CSV file with review decisions"),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Import review decisions from CSV and promote saved candidates to watchlist."""
    try:
        db_path = database_path or config.database_path

        if not Path(file).exists():
            console.print(f"[bold red]Error:[/bold red] File not found: {file}")
            raise typer.Exit(code=1)

        console.print(f"[bold blue]Processing review decisions from {file}...[/bold blue]")

        counts = process_review_decisions(file, db_path)

        console.print(f"\n[bold green]SUCCESS:[/bold green] Processed {counts['processed']}/{counts['total']} decisions")
        console.print(f"  - Saved: {counts['save']} ({counts['promoted']} promoted to watchlist)")
        console.print(f"  - Rejected: {counts['reject']}")
        console.print(f"  - Maybe: {counts['maybe']}")
        console.print(f"  - Hold for more data: {counts['hold_for_more_data']}")

        if counts['invalid'] > 0:
            console.print(f"  - [yellow]Invalid decisions:[/yellow] {counts['invalid']}")
        if counts['errors'] > 0:
            console.print(f"  - [red]Errors:[/red] {counts['errors']}")

        console.print("\n[dim]Run 'marketsentry list-watched' to see promoted properties[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Import review error: {e}")
        raise typer.Exit(code=1)


@app.command()
def list_candidates(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of candidates to show"),
) -> None:
    """List candidates from review queue."""
    try:
        db_path = database_path or config.database_path

        candidates = get_all_candidates(db_path)

        if not candidates:
            console.print("[yellow]No candidates found in review queue[/yellow]")
            return

        # Create table
        table = Table(title=f"Candidate Review Queue ({len(candidates)} total, showing {min(limit, len(candidates))})")
        table.add_column("ID", style="cyan")
        table.add_column("Address", style="magenta")
        table.add_column("City", style="blue")
        table.add_column("Price", justify="right")
        table.add_column("Quiet", justify="right")
        table.add_column("Vibrancy", justify="right")
        table.add_column("Decision")

        for candidate in candidates[:limit]:
            price_str = f"${candidate.get('price', 0):,.0f}" if candidate.get('price') else "N/A"
            quiet_str = f"{candidate.get('quiet_score', 0):.1f}" if candidate.get('quiet_score') else "N/A"
            vibrancy_str = f"{candidate.get('vibrancy_score', 0):.1f}" if candidate.get('vibrancy_score') else "N/A"
            decision_str = candidate.get('user_decision', 'pending')

            table.add_row(
                str(candidate.get('candidate_id')),
                candidate.get('address', ''),
                candidate.get('city', ''),
                price_str,
                quiet_str,
                vibrancy_str,
                decision_str,
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"List candidates error: {e}")
        raise typer.Exit(code=1)


@app.command()
def list_watched(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of properties to show"),
) -> None:
    """List watched properties."""
    try:
        db_path = database_path or config.database_path

        properties = get_active_watched_properties(db_path)

        if not properties:
            console.print("[yellow]No watched properties found[/yellow]")
            console.print("\n[dim]Import reviewed candidates with 'marketsentry import-review' to add properties[/dim]")
            return

        # Create table
        table = Table(title=f"Watched Properties ({len(properties)} active)")
        table.add_column("ID", style="cyan")
        table.add_column("Address", style="magenta")
        table.add_column("City", style="blue")
        table.add_column("Price", justify="right")
        table.add_column("Priority")
        table.add_column("Quiet", justify="right")
        table.add_column("DOM Delta", justify="right")

        for prop in properties[:limit]:
            price_str = f"${prop.get('current_price', 0):,.0f}" if prop.get('current_price') else "N/A"
            priority = prop.get('watch_priority', 2)
            priority_str = "HIGH" if priority == 3 else "MED" if priority == 2 else "LOW"
            quiet_str = f"{prop.get('quiet_score', 0):.1f}" if prop.get('quiet_score') else "N/A"
            dom_delta = prop.get('effective_dom_delta')
            dom_delta_str = f"+{dom_delta}" if dom_delta else "N/A"

            table.add_row(
                str(prop.get('property_id')),
                prop.get('address', ''),
                prop.get('city', ''),
                price_str,
                priority_str,
                quiet_str,
                dom_delta_str,
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"List watched properties error: {e}")
        raise typer.Exit(code=1)


@app.command()
def import_redfin_urls(
    file: str = typer.Option(..., "--file", "-f", help="CSV file with Redfin URLs"),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Import Redfin property URLs from CSV file."""
    try:
        db_path = database_path or config.database_path

        if not Path(file).exists():
            console.print(f"[bold red]Error:[/bold red] File not found: {file}")
            raise typer.Exit(code=1)

        console.print(f"[bold blue]Importing Redfin URLs from {file}...[/bold blue]")

        result = import_redfin_urls_from_csv(file, db_path)

        console.print(
            f"\n[bold green]SUCCESS:[/bold green] Processed {result.total_rows_read} rows"
        )
        console.print(f"  - Candidates inserted: {result.candidates_inserted}")
        console.print(f"  - Candidates skipped (duplicates): {result.candidates_skipped}")
        console.print(f"  - Rows rejected: {result.rows_rejected}")

        if result.parse_warnings > 0:
            console.print(f"  - [yellow]Warnings:[/yellow] {result.parse_warnings}")
        if result.parse_errors > 0:
            console.print(f"  - [red]Errors:[/red] {result.parse_errors}")

        console.print("\n[dim]Run 'marketsentry list-candidates' to see imported candidates[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Import Redfin URLs error: {e}")
        raise typer.Exit(code=1)


@app.command()
def parse_redfin_fixtures(
    directory: str = typer.Option(
        ..., "--dir", "-d", help="Directory containing HTML fixtures"
    ),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Parse saved Redfin HTML fixtures and extract candidates."""
    try:
        db_path = database_path or config.database_path

        if not Path(directory).exists():
            console.print(f"[bold red]Error:[/bold red] Directory not found: {directory}")
            raise typer.Exit(code=1)

        if not Path(directory).is_dir():
            console.print(f"[bold red]Error:[/bold red] Not a directory: {directory}")
            raise typer.Exit(code=1)

        console.print(
            f"[bold blue]Parsing Redfin HTML fixtures from {directory}...[/bold blue]"
        )

        result = parse_redfin_fixtures_from_directory(directory, db_path)

        console.print(
            f"\n[bold green]SUCCESS:[/bold green] Processed {result.total_rows_read} HTML files"
        )
        console.print(f"  - Candidates inserted: {result.candidates_inserted}")
        console.print(f"  - Candidates skipped (duplicates): {result.candidates_skipped}")
        console.print(f"  - Files rejected: {result.rows_rejected}")

        if result.parse_warnings > 0:
            console.print(f"  - [yellow]Parse warnings:[/yellow] {result.parse_warnings}")
        if result.parse_errors > 0:
            console.print(f"  - [red]Parse errors:[/red] {result.parse_errors}")

        console.print("\n[dim]Run 'marketsentry list-candidates' to see extracted candidates[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Parse Redfin fixtures error: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
