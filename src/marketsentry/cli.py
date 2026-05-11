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
    migrate_schema,
    table_exists,
)
from marketsentry.logging_config import logger
from marketsentry.review_export import export_candidates_from_db
from marketsentry.review_import import process_review_decisions
from marketsentry.sample_data import seed_sample_candidates
from marketsentry.redfin_url_import import import_redfin_urls_from_csv
from marketsentry.redfin_fixture_parser import parse_redfin_fixtures_from_directory
from marketsentry.redfin_detail_parser import parse_redfin_detail_directory
from marketsentry.redfin_detail_enrichment import enrich_candidates_from_detail_directory

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

        # Apply schema migrations for existing databases
        migrate_schema(db_path)

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


@app.command()
def parse_redfin_details(
    directory: str = typer.Option(
        ..., "--dir", "-d", help="Directory containing Redfin detail HTML files"
    ),
) -> None:
    """Parse Redfin property detail HTML files and display summary."""
    try:
        if not Path(directory).exists():
            console.print(f"[bold red]Error:[/bold red] Directory not found: {directory}")
            raise typer.Exit(code=1)

        if not Path(directory).is_dir():
            console.print(f"[bold red]Error:[/bold red] Not a directory: {directory}")
            raise typer.Exit(code=1)

        console.print(
            f"[bold blue]Parsing Redfin detail files from {directory}...[/bold blue]"
        )

        results = parse_redfin_detail_directory(Path(directory))

        success_count = sum(1 for r in results if r.parse_status in ["success", "partial"])
        failed_count = sum(1 for r in results if r.parse_status == "failed")
        total_warnings = sum(len(r.warnings) for r in results)
        total_errors = sum(len(r.errors) for r in results)

        console.print(
            f"\n[bold green]Parsed {len(results)} files:[/bold green]"
        )
        console.print(f"  - Successful: {success_count}")
        console.print(f"  - Failed: {failed_count}")

        if total_warnings > 0:
            console.print(f"  - [yellow]Total warnings:[/yellow] {total_warnings}")
        if total_errors > 0:
            console.print(f"  - [red]Total errors:[/red] {total_errors}")

        # Show sample details
        console.print(f"\n[bold]Sample parsed details:[/bold]")
        for i, result in enumerate(results[:3]):  # Show first 3
            if result.property_detail:
                detail = result.property_detail
                console.print(f"\n{i+1}. {detail.address or 'Unknown address'}")
                if detail.facts:
                    console.print(f"   Price: ${detail.facts.price:,.0f}" if detail.facts.price else "   Price: N/A")
                    console.print(f"   Beds/Baths: {detail.facts.beds or 'N/A'}/{detail.facts.baths or 'N/A'}")
                if detail.lifestyle_scores:
                    console.print(f"   Quiet: {detail.lifestyle_scores.quiet_score}/10" if detail.lifestyle_scores.quiet_score else "   Quiet: N/A")
                if detail.listing_history:
                    console.print(f"   Listing events: {len(detail.listing_history)}")

        console.print("\n[dim]Note: This command only parses and displays. Use 'enrich-redfin-details' to update candidates.[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Parse Redfin details error: {e}")
        raise typer.Exit(code=1)


@app.command()
def enrich_redfin_details(
    directory: str = typer.Option(
        ..., "--dir", "-d", help="Directory containing Redfin detail HTML files"
    ),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Parse Redfin detail files and enrich candidate records."""
    try:
        db_path = database_path or config.database_path

        if not Path(directory).exists():
            console.print(f"[bold red]Error:[/bold red] Directory not found: {directory}")
            raise typer.Exit(code=1)

        if not Path(directory).is_dir():
            console.print(f"[bold red]Error:[/bold red] Not a directory: {directory}")
            raise typer.Exit(code=1)

        console.print(
            f"[bold blue]Enriching candidates from detail files in {directory}...[/bold blue]"
        )

        result = enrich_candidates_from_detail_directory(directory, db_path)

        console.print(
            f"\n[bold green]SUCCESS:[/bold green] Processed {result.total_files_processed} files"
        )
        console.print(f"  - Details parsed: {result.details_parsed}")
        console.print(f"  - Candidates matched: {result.candidates_matched}")
        console.print(f"  - Candidates updated: {result.candidates_updated}")
        console.print(f"  - Listing events inserted: {result.listing_events_inserted}")

        if result.listing_events_skipped > 0:
            console.print(f"  - Listing events skipped (duplicates): {result.listing_events_skipped}")

        if result.parse_warnings > 0:
            console.print(f"  - [yellow]Parse warnings:[/yellow] {result.parse_warnings}")
        if result.parse_errors > 0:
            console.print(f"  - [red]Parse errors:[/red] {result.parse_errors}")

        console.print("\n[dim]Run 'marketsentry list-candidates' to see enriched candidates[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Enrich Redfin details error: {e}")
        raise typer.Exit(code=1)


@app.command()
def recalc_candidates(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Recalculate Effective DOM and scoring metrics for all candidates."""
    from marketsentry.candidate_recalc import recalculate_candidates

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Recalculating candidate metrics...[/bold blue]")

        result = recalculate_candidates(db_path)

        console.print(f"\n[bold green]SUCCESS:[/bold green] Recalculation complete")
        console.print(f"  - Candidates scanned: {result.candidates_scanned}")
        console.print(f"  - Candidates updated: {result.candidates_updated}")
        console.print(f"  - Listing events used: {result.listing_events_used}")

        if result.warnings:
            console.print(f"\n[yellow]Warnings ({len(result.warnings)}):[/yellow]")
            for warning in result.warnings[:5]:  # Show first 5
                console.print(f"  - {warning}")
            if len(result.warnings) > 5:
                console.print(f"  ... and {len(result.warnings) - 5} more")

        if result.errors:
            console.print(f"\n[red]Errors ({len(result.errors)}):[/red]")
            for error in result.errors[:5]:  # Show first 5
                console.print(f"  - {error}")
            if len(result.errors) > 5:
                console.print(f"  ... and {len(result.errors) - 5} more")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Recalculation error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_analysis_report(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (default: timestamped file in data/exports/)"
    ),
    markdown: bool = typer.Option(
        False, "--markdown", "-m", help="Also export Markdown summary"
    ),
) -> None:
    """Export candidate analysis report to CSV."""
    from marketsentry.candidate_report import (
        export_candidate_analysis_report,
        export_markdown_summary,
    )

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Exporting candidate analysis report...[/bold blue]")

        # Export CSV report
        csv_path = export_candidate_analysis_report(db_path, output)

        # Count rows
        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            row_count = sum(1 for row in csv.DictReader(f))

        console.print(f"\n[bold green]SUCCESS:[/bold green] Report exported")
        console.print(f"  - Output file: {csv_path}")
        console.print(f"  - Rows: {row_count}")

        # Export markdown if requested
        if markdown:
            md_path = export_markdown_summary(db_path)
            console.print(f"  - Markdown summary: {md_path}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export analysis report error: {e}")
        raise typer.Exit(code=1)


@app.command()
def import_cross_site_urls(
    file: str = typer.Option(..., "--file", "-f", help="CSV file with cross-site URLs"),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Import cross-site URLs from CSV and link to watched properties."""
    from marketsentry.cross_site_url_import import import_cross_site_urls_from_csv

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Importing cross-site URLs...[/bold blue]")

        result = import_cross_site_urls_from_csv(file, db_path)

        console.print(f"\n[bold green]SUCCESS:[/bold green] Import complete")
        console.print(f"  - Rows processed: {result.total_rows_read}")
        console.print(f"  - Properties matched: {result.properties_matched}")
        console.print(f"  - Properties updated: {result.properties_updated}")
        console.print(f"  - Rows skipped: {result.rows_skipped}")

        if result.errors:
            console.print(f"\n[yellow]Errors ({len(result.errors)}):[/yellow]")
            for error in result.errors[:5]:  # Show first 5 errors
                console.print(f"  - {error}")
            if len(result.errors) > 5:
                console.print(f"  ... and {len(result.errors) - 5} more")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Import cross-site URLs error: {e}")
        raise typer.Exit(code=1)


@app.command()
def parse_cross_site_fixtures(
    source: str = typer.Option(..., "--source", "-s", help="Source site (zillow, realtor, homes, compass)"),
    directory: str = typer.Option(..., "--dir", "-d", help="Directory containing HTML fixtures"),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Parse cross-site HTML fixtures and create observations."""
    from marketsentry.cross_site_enrichment import parse_cross_site_directory

    try:
        db_path = database_path or config.database_path

        # Validate source
        valid_sources = ["zillow", "realtor", "homes", "compass"]
        if source not in valid_sources:
            console.print(f"[bold red]Error:[/bold red] Invalid source '{source}'. Must be one of: {', '.join(valid_sources)}")
            raise typer.Exit(code=1)

        console.print(f"[bold blue]Parsing {source} fixtures from {directory}...[/bold blue]")

        result = parse_cross_site_directory(directory, source, db_path)

        console.print(f"\n[bold green]SUCCESS:[/bold green] Enrichment complete")
        console.print(f"  - Files processed: {result.files_processed}")
        console.print(f"  - Observations created: {result.observations_created}")
        console.print(f"  - Properties matched: {result.properties_matched}")
        console.print(f"  - Parse errors: {result.parse_errors}")

        if result.errors:
            console.print(f"\n[yellow]Errors ({len(result.errors)}):[/yellow]")
            for error in result.errors[:5]:
                console.print(f"  - {error}")
            if len(result.errors) > 5:
                console.print(f"  ... and {len(result.errors) - 5} more")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Parse cross-site fixtures error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_cross_site_report(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (default: timestamped file in data/exports/)"
    ),
) -> None:
    """Export cross-site comparison report to CSV."""
    from marketsentry.cross_site_report import export_cross_site_comparison_report

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Exporting cross-site comparison report...[/bold blue]")

        # Export CSV report
        csv_path = export_cross_site_comparison_report(db_path, output)

        # Count rows
        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            row_count = sum(1 for row in csv.DictReader(f))

        console.print(f"\n[bold green]SUCCESS:[/bold green] Report exported")
        console.print(f"  - Output file: {csv_path}")
        console.print(f"  - Properties: {row_count}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export cross-site report error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_cross_site_analytics_report(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (default: timestamped file in data/exports/)"
    ),
) -> None:
    """Export confidence-weighted cross-site analytics report to CSV."""
    from marketsentry.cross_site_analytics_report import (
        export_cross_site_analytics_report as _export,
    )

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Exporting cross-site analytics report...[/bold blue]")

        csv_path = _export(database_path=db_path, output_path=output)

        # Count rows
        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            row_count = sum(1 for row in csv.DictReader(f))

        console.print(f"\n[bold green]SUCCESS:[/bold green] Analytics report exported")
        console.print(f"  - Output file: {csv_path}")
        console.print(f"  - Properties: {row_count}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export cross-site analytics report error: {e}")
        raise typer.Exit(code=1)


@app.command()
def snapshot_cross_site_analytics(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    force: bool = typer.Option(
        False, "--force", help="Force snapshot even without material change"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Output directory for reports"
    ),
) -> None:
    """Create cross-site analytics trend snapshots for all watched properties."""
    from marketsentry.cross_site_trends import create_cross_site_analytics_snapshots

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Creating cross-site analytics snapshots...[/bold blue]")

        result = create_cross_site_analytics_snapshots(
            database_path=db_path, force=force
        )

        console.print(f"\n[bold green]Snapshot run complete[/bold green]")
        console.print(f"  - Properties scanned: {result.properties_scanned}")
        console.print(f"  - Analytics computed: {result.analytics_computed}")
        console.print(f"  - Snapshots created: {result.snapshots_created}")
        console.print(f"  - Snapshots skipped (no change): {result.snapshots_skipped_no_change}")
        console.print(f"  - Trend changes detected: {result.trend_changes_detected}")

        if result.warnings:
            console.print(f"  - Warnings: {len(result.warnings)}")
            for w in result.warnings:
                console.print(f"    [yellow]{w}[/yellow]")

        if result.errors:
            console.print(f"  - Errors: {len(result.errors)}")
            for e in result.errors:
                console.print(f"    [red]{e}[/red]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Snapshot cross-site analytics error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_cross_site_trend_report(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Output directory"
    ),
) -> None:
    """Export cross-site analytics trend report to CSV."""
    from marketsentry.cross_site_trends import export_cross_site_trend_report as _export

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Exporting cross-site trend report...[/bold blue]")

        output_path = None
        if output_dir:
            from datetime import datetime as dt
            ts = dt.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(Path(output_dir) / f"cross_site_trends_{ts}.csv")

        csv_path = _export(database_path=db_path, output_path=output_path)

        # Count rows
        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            row_count = sum(1 for row in csv.DictReader(f))

        console.print(f"\n[bold green]SUCCESS:[/bold green] Trend report exported")
        console.print(f"  - Output file: {csv_path}")
        console.print(f"  - Properties: {row_count}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export cross-site trend report error: {e}")
        raise typer.Exit(code=1)


@app.command()
def generate_cross_site_trend_alerts(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Output directory (optional)"
    ),
) -> None:
    """Generate cross-site trend alerts from snapshot comparisons."""
    from marketsentry.cross_site_trend_alerts import (
        generate_cross_site_trend_alerts as _generate,
    )

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Generating cross-site trend alerts...[/bold blue]")

        result = _generate(database_path=db_path, output_dir=output_dir)

        console.print(f"\n[bold green]Alert generation complete[/bold green]")
        console.print(f"  - Properties scanned: {result.properties_scanned}")
        console.print(f"  - Alerts generated: {result.alerts_generated}")
        console.print(f"  - Duplicates skipped: {result.duplicates_skipped}")

        if result.warnings:
            console.print(f"  - Warnings: {len(result.warnings)}")
            for w in result.warnings:
                console.print(f"    [yellow]{w}[/yellow]")

        if result.errors:
            console.print(f"  - Errors: {len(result.errors)}")
            for e in result.errors:
                console.print(f"    [red]{e}[/red]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Generate cross-site trend alerts error: {e}")
        raise typer.Exit(code=1)


@app.command()
def list_cross_site_trend_alerts(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    status: Optional[str] = typer.Option(
        None, "--status", help="Filter by alert status (default: open)"
    ),
    severity: Optional[str] = typer.Option(
        None, "--severity", help="Filter by severity"
    ),
    property_id: Optional[int] = typer.Option(
        None, "--property-id", "-p", help="Filter by property ID"
    ),
) -> None:
    """List cross-site trend alerts with optional filters."""
    from marketsentry.cross_site_trend_alerts import (
        list_cross_site_trend_alerts as _list_alerts,
    )

    try:
        db_path = database_path or config.database_path

        alerts = _list_alerts(
            database_path=db_path,
            status_filter=status,
            severity_filter=severity,
            property_id=property_id,
        )

        if not alerts:
            console.print("[dim]No alerts found matching filters.[/dim]")
            return

        table = Table(title="Cross-Site Trend Alerts")
        table.add_column("ID", style="cyan")
        table.add_column("Property", style="white")
        table.add_column("Type", style="white")
        table.add_column("Severity", style="white")
        table.add_column("Status", style="white")
        table.add_column("Message", style="white")
        table.add_column("Created", style="dim")

        for alert in alerts:
            sev_style = {
                "critical": "bold red",
                "high": "red",
                "warning": "yellow",
                "info": "green",
            }.get(alert.severity, "white")

            table.add_row(
                str(alert.alert_id),
                str(alert.property_id),
                alert.alert_type,
                f"[{sev_style}]{alert.severity}[/{sev_style}]",
                alert.alert_status,
                (alert.message or "")[:60],
                str(alert.created_at)[:19] if alert.created_at else "",
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(alerts)} alerts[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"List cross-site trend alerts error: {e}")
        raise typer.Exit(code=1)


@app.command()
def acknowledge_cross_site_trend_alert(
    alert_id: int = typer.Option(..., "--alert-id", help="Alert ID to acknowledge"),
    notes: Optional[str] = typer.Option(
        None, "--notes", help="Optional notes"
    ),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Acknowledge a cross-site trend alert."""
    from marketsentry.cross_site_trend_alerts import (
        acknowledge_cross_site_trend_alert as _ack,
    )

    try:
        db_path = database_path or config.database_path

        updated = _ack(alert_id=alert_id, notes=notes, database_path=db_path)

        if updated:
            console.print(
                f"[bold green]Alert {alert_id} acknowledged[/bold green]"
            )
        else:
            console.print(
                f"[bold yellow]Alert {alert_id} not found or already updated[/bold yellow]"
            )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Acknowledge cross-site trend alert error: {e}")
        raise typer.Exit(code=1)


@app.command()
def resolve_cross_site_trend_alert(
    alert_id: int = typer.Option(..., "--alert-id", help="Alert ID to resolve"),
    notes: Optional[str] = typer.Option(
        None, "--notes", help="Optional notes"
    ),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Resolve a cross-site trend alert."""
    from marketsentry.cross_site_trend_alerts import (
        resolve_cross_site_trend_alert as _resolve,
    )

    try:
        db_path = database_path or config.database_path

        updated = _resolve(alert_id=alert_id, notes=notes, database_path=db_path)

        if updated:
            console.print(
                f"[bold green]Alert {alert_id} resolved[/bold green]"
            )
        else:
            console.print(
                f"[bold yellow]Alert {alert_id} not found or already updated[/bold yellow]"
            )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Resolve cross-site trend alert error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_cross_site_trend_alerts_report(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Output directory"
    ),
    status: Optional[str] = typer.Option(
        None, "--status", help="Filter by alert status"
    ),
) -> None:
    """Export cross-site trend alerts report to CSV."""
    from marketsentry.cross_site_trend_alerts import (
        export_cross_site_trend_alerts_report as _export,
    )

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Exporting cross-site trend alerts report...[/bold blue]")

        output_path = None
        if output_dir:
            from datetime import datetime as dt
            ts = dt.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(Path(output_dir) / f"cross_site_trend_alerts_{ts}.csv")

        csv_path = _export(
            database_path=db_path, output_path=output_path, status_filter=status
        )

        # Count rows
        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            row_count = sum(1 for row in csv.DictReader(f))

        console.print(f"\n[bold green]SUCCESS:[/bold green] Alerts report exported")
        console.print(f"  - Output file: {csv_path}")
        console.print(f"  - Alerts: {row_count}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export cross-site trend alerts report error: {e}")
        raise typer.Exit(code=1)


@app.command()
def cross_site_alert_analytics_summary(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Show cross-site alert analytics summary across all properties."""
    from marketsentry.cross_site_alert_analytics import (
        summarize_alert_history_for_all_properties,
    )

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Computing cross-site alert analytics...[/bold blue]")

        agg = summarize_alert_history_for_all_properties(database_path=db_path)

        console.print(f"\n[bold green]Alert Analytics Summary[/bold green]")
        console.print(f"  - Total properties with alerts: {agg.total_properties_with_alerts}")
        console.print(f"  - Properties with open alerts: {agg.properties_with_open_alerts}")
        console.print(f"  - Properties with high/critical alerts: {agg.properties_with_high_critical_alerts}")
        console.print(f"  - Properties with repeated patterns: {agg.properties_with_repeated_patterns}")

        if agg.top_alert_types:
            console.print(f"  - Top alert types: {', '.join(agg.top_alert_types)}")

        if agg.top_burden_properties:
            console.print(f"  - Top burden properties: {', '.join(str(p) for p in agg.top_burden_properties)}")

        if agg.oldest_open_alert_age_days is not None:
            console.print(f"  - Oldest open alert: {agg.oldest_open_alert_age_days} days")

        # Per-property burden table
        if agg.summaries:
            table = Table(title="Property Alert Burden")
            table.add_column("Property", style="cyan")
            table.add_column("Address", style="white")
            table.add_column("Open", style="white")
            table.add_column("High/Crit", style="white")
            table.add_column("Burden", style="white")
            table.add_column("Patterns", style="white")
            table.add_column("Action", style="dim")

            for s in sorted(
                agg.summaries,
                key=lambda x: x.burden.alert_burden_score,
                reverse=True,
            ):
                burden_style = {
                    "elevated_review": "bold red",
                    "high": "red",
                    "moderate": "yellow",
                    "low": "green",
                    "none": "dim",
                }.get(s.burden.alert_burden_label, "white")

                table.add_row(
                    str(s.property_id),
                    s.address or "",
                    str(s.burden.open_alert_count),
                    str(s.burden.high_or_critical_open_alert_count),
                    f"[{burden_style}]{s.burden.alert_burden_label}[/{burden_style}]",
                    str(len(s.patterns)),
                    (s.recommended_review_action or "")[:50],
                )

            console.print(table)

        # Recommended next actions
        if agg.properties_with_high_critical_alerts > 0:
            console.print(
                f"\n[yellow]Recommended:[/yellow] Review {agg.properties_with_high_critical_alerts} "
                f"properties with high/critical alerts"
            )
        if agg.properties_with_repeated_patterns > 0:
            console.print(
                f"[yellow]Recommended:[/yellow] Investigate {agg.properties_with_repeated_patterns} "
                f"properties with repeated alert patterns"
            )

        if agg.errors:
            for e in agg.errors:
                console.print(f"  [red]{e}[/red]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Cross-site alert analytics summary error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_cross_site_alert_analytics_report(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Output directory"
    ),
    include_resolved: bool = typer.Option(
        True, "--include-resolved", help="Include resolved alerts"
    ),
) -> None:
    """Export cross-site alert analytics report to CSV."""
    from marketsentry.cross_site_alert_analytics import (
        export_cross_site_alert_analytics_report as _export,
    )

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Exporting cross-site alert analytics report...[/bold blue]")

        output_path = None
        if output_dir:
            from datetime import datetime as dt
            ts = dt.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(
                Path(output_dir) / f"cross_site_alert_analytics_{ts}.csv"
            )

        csv_path = _export(
            database_path=db_path,
            output_path=output_path,
            include_resolved=include_resolved,
        )

        # Count rows
        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            row_count = sum(1 for row in csv.DictReader(f))

        console.print(f"\n[bold green]SUCCESS:[/bold green] Alert analytics report exported")
        console.print(f"  - Output file: {csv_path}")
        console.print(f"  - Properties: {row_count}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export cross-site alert analytics report error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_cross_site_alert_triage(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Output directory"
    ),
    status: Optional[str] = typer.Option(
        "open", "--status", help="Alert status filter (default: open)"
    ),
    severity: Optional[str] = typer.Option(
        None, "--severity", help="Alert severity filter"
    ),
    property_id: Optional[int] = typer.Option(
        None, "--property-id", help="Filter by property ID"
    ),
    include_acknowledged: bool = typer.Option(
        False, "--include-acknowledged", help="Include acknowledged alerts"
    ),
) -> None:
    """Export cross-site alerts to a triage CSV for offline review."""
    from marketsentry.cross_site_alert_triage import (
        export_cross_site_alert_triage_csv,
        ALLOWED_TRIAGE_DECISIONS,
    )

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Exporting cross-site alert triage CSV...[/bold blue]")

        output_path = None
        if output_dir:
            from datetime import datetime as dt
            ts = dt.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(
                Path(output_dir) / f"cross_site_alert_triage_{ts}.csv"
            )

        result = export_cross_site_alert_triage_csv(
            database_path=db_path,
            output_path=output_path,
            status_filter=status,
            severity_filter=severity,
            property_id=property_id,
            include_acknowledged=include_acknowledged,
        )

        console.print(f"\n[bold green]SUCCESS:[/bold green] Triage CSV exported")
        console.print(f"  - Output file: {result.output_path}")
        console.print(f"  - Alert rows: {result.row_count}")
        console.print(f"  - Triage export ID: {result.triage_export_id}")
        console.print(f"  - Allowed decisions: {', '.join(sorted(ALLOWED_TRIAGE_DECISIONS))}")
        console.print(
            "\nEdit the triage_decision column in the CSV, then import with: "
            "marketsentry import-cross-site-alert-triage --file <path>"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export cross-site alert triage error: {e}")
        raise typer.Exit(code=1)


@app.command()
def import_cross_site_alert_triage(
    file: str = typer.Option(
        ..., "--file", help="Path to the triage CSV file"
    ),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    force_status_mismatch: bool = typer.Option(
        False, "--force-status-mismatch",
        help="Allow applying decisions even if alert status has changed"
    ),
) -> None:
    """Import triage CSV and apply decisions to cross-site alerts."""
    from marketsentry.cross_site_alert_triage import (
        apply_cross_site_alert_triage_decisions,
    )

    try:
        db_path = database_path or config.database_path

        console.print(f"[bold blue]Importing triage decisions from:[/bold blue] {file}")

        result = apply_cross_site_alert_triage_decisions(
            file_path=file,
            database_path=db_path,
            force_status_mismatch=force_status_mismatch,
        )

        console.print(f"\n[bold green]SUCCESS:[/bold green] Triage import complete")
        console.print(f"  - Rows read: {result.rows_read}")
        console.print(f"  - Valid decisions: {result.valid_decisions}")
        console.print(f"  - Acknowledged: {result.acknowledged}")
        console.print(f"  - Resolved: {result.resolved}")
        console.print(f"  - Archived: {result.archived}")
        console.print(f"  - Kept open: {result.kept_open}")
        console.print(f"  - Needs reparse: {result.needs_reparse}")
        console.print(f"  - Needs manual review: {result.needs_manual_review}")

        if result.skipped_status_mismatch > 0:
            console.print(
                f"  - [yellow]Skipped (status mismatch): "
                f"{result.skipped_status_mismatch}[/yellow]"
            )

        if result.invalid_rows > 0:
            console.print(f"  - [red]Invalid rows: {result.invalid_rows}[/red]")

        if result.errors:
            console.print("[yellow]Errors:[/yellow]")
            for err in result.errors[:10]:
                console.print(f"    - {err}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Import cross-site alert triage error: {e}")
        raise typer.Exit(code=1)


@app.command()
def cross_site_alert_hygiene_check(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Output directory for reports"
    ),
    report_format: str = typer.Option(
        "both", "--format", help="Report format: csv, md, or both (default: both)"
    ),
    open_stale_days: int = typer.Option(
        7, "--open-stale-days", help="Days before open alerts are flagged stale"
    ),
    acknowledged_stale_days: int = typer.Option(
        14, "--ack-stale-days", help="Days before acknowledged alerts are flagged"
    ),
    resolved_archive_days: int = typer.Option(
        30, "--resolved-archive-days", help="Days before resolved alerts become archive candidates"
    ),
) -> None:
    """Run alert hygiene checks and generate a report.

    Identifies stale open alerts, old acknowledged/resolved alerts,
    pending reparse/manual review items, high-burden properties,
    and repeated unresolved patterns. Report-only: does not
    auto-archive alerts or change watchlist status.
    """
    from marketsentry.cross_site_alert_hygiene import (
        export_cross_site_alert_hygiene_report,
    )
    from marketsentry.models import CrossSiteAlertHygieneConfig

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Running cross-site alert hygiene check...[/bold blue]")

        hygiene_config = CrossSiteAlertHygieneConfig(
            open_stale_days=open_stale_days,
            acknowledged_stale_days=acknowledged_stale_days,
            resolved_archive_days=resolved_archive_days,
        )

        result = export_cross_site_alert_hygiene_report(
            database_path=db_path,
            config=hygiene_config,
            exports_dir=output_dir,
            report_format=report_format,
        )

        console.print(f"\n[bold green]SUCCESS:[/bold green] Hygiene check complete")
        console.print(f"  - Total issues found: {result.summary.total_issues}")
        console.print(f"  - Stale open alerts: {result.summary.stale_open_alerts}")
        console.print(f"  - Stale acknowledged: {result.summary.stale_acknowledged_alerts}")
        console.print(f"  - Archive candidates: {result.summary.resolved_archive_candidates}")
        console.print(f"  - Needs reparse: {result.summary.needs_reparse_pending}")
        console.print(f"  - Needs manual review: {result.summary.needs_manual_review_pending}")
        console.print(f"  - High-burden properties: {result.summary.high_burden_properties}")
        console.print(f"  - Repeated unresolved: {result.summary.repeated_unresolved_patterns}")

        if result.csv_path:
            console.print(f"  - CSV report: {result.csv_path}")
        if result.md_path:
            console.print(f"  - Markdown report: {result.md_path}")

        if result.summary.next_actions:
            console.print("\n[bold]Recommended next actions:[/bold]")
            for action in result.summary.next_actions[:10]:
                console.print(f"  - {action}")

        if result.warnings:
            console.print(f"\n[yellow]Warnings ({len(result.warnings)}):[/yellow]")
            for w in result.warnings[:5]:
                console.print(f"  - {w}")

        if result.errors:
            console.print(f"\n[red]Errors ({len(result.errors)}):[/red]")
            for err in result.errors[:5]:
                console.print(f"  - {err}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Cross-site alert hygiene check error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_cross_site_alert_hygiene_report(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output_path: Optional[str] = typer.Option(
        None, "--output", help="Output file path"
    ),
    report_format: str = typer.Option(
        "csv", "--format", help="Report format: csv, md, or both (default: csv)"
    ),
) -> None:
    """Export an alert hygiene report to CSV or Markdown.

    Report-only: does not auto-archive alerts, change watchlist
    status, or modify Quiet Score gatekeeper results.
    """
    from marketsentry.cross_site_alert_hygiene import (
        export_cross_site_alert_hygiene_report as _export_hygiene,
    )

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Exporting alert hygiene report...[/bold blue]")

        result = _export_hygiene(
            database_path=db_path,
            output_path=output_path,
            report_format=report_format,
        )

        console.print(f"\n[bold green]SUCCESS:[/bold green] Hygiene report exported")
        console.print(f"  - Issues found: {result.summary.total_issues}")

        if result.csv_path:
            console.print(f"  - CSV report: {result.csv_path}")
        if result.md_path:
            console.print(f"  - Markdown report: {result.md_path}")

        if result.warnings:
            console.print(f"\n[yellow]Warnings ({len(result.warnings)}):[/yellow]")
            for w in result.warnings[:5]:
                console.print(f"  - {w}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export alert hygiene report error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_cross_site_alert_archive_candidates(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Output directory"
    ),
    resolved_age_days: int = typer.Option(
        30, "--resolved-age-days", help="Minimum age in days for candidates"
    ),
    property_id: Optional[int] = typer.Option(
        None, "--property-id", help="Filter by property ID"
    ),
    severity: Optional[str] = typer.Option(
        None, "--severity", help="Filter by severity"
    ),
) -> None:
    """Export resolved alerts eligible for archive review to CSV.

    Opt-in archive workflow: does not auto-archive. The user
    reviews the CSV and chooses archive, keep_resolved, reopen,
    or no_archive for each alert.
    """
    from marketsentry.cross_site_alert_archive_policy import (
        ALLOWED_ARCHIVE_DECISIONS,
        export_cross_site_alert_archive_candidates as _export_archive,
    )

    try:
        db_path = database_path or config.database_path

        console.print(
            "[bold blue]Exporting archive candidate CSV...[/bold blue]"
        )

        result = _export_archive(
            database_path=db_path,
            resolved_age_days=resolved_age_days,
            property_id=property_id,
            severity=severity,
            exports_dir=output_dir,
        )

        console.print(f"\n[bold green]SUCCESS:[/bold green] Archive candidates exported")
        console.print(f"  - Output file: {result.output_path}")
        console.print(f"  - Candidate rows: {result.row_count}")
        console.print(f"  - Archive export ID: {result.archive_export_id}")
        console.print(f"  - Resolved age threshold: {result.resolved_age_days} days")
        console.print(
            f"  - Allowed decisions: {', '.join(sorted(ALLOWED_ARCHIVE_DECISIONS))}"
        )
        console.print(
            "\nEdit the archive_decision column in the CSV, then import with: "
            "marketsentry import-cross-site-alert-archive-decisions --file <path>"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export archive candidates error: {e}")
        raise typer.Exit(code=1)


@app.command()
def import_cross_site_alert_archive_decisions(
    file: str = typer.Option(
        ..., "--file", help="Path to the archive CSV file"
    ),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    force_status_mismatch: bool = typer.Option(
        False, "--force-status-mismatch",
        help="Allow applying decisions even if alert status has changed"
    ),
) -> None:
    """Import archive CSV and apply decisions to resolved alerts.

    Opt-in only: only applies decisions the user has explicitly set.
    """
    from marketsentry.cross_site_alert_archive_policy import (
        apply_cross_site_alert_archive_decisions,
    )

    try:
        db_path = database_path or config.database_path

        console.print(
            f"[bold blue]Importing archive decisions from:[/bold blue] {file}"
        )

        result = apply_cross_site_alert_archive_decisions(
            file_path=file,
            database_path=db_path,
            force_status_mismatch=force_status_mismatch,
        )

        console.print(f"\n[bold green]SUCCESS:[/bold green] Archive import complete")
        console.print(f"  - Rows read: {result.rows_read}")
        console.print(f"  - Valid decisions: {result.valid_decisions}")
        console.print(f"  - Archived: {result.archived}")
        console.print(f"  - Reopened: {result.reopened}")
        console.print(f"  - Kept resolved: {result.kept_resolved}")
        console.print(f"  - No archive: {result.no_archive}")

        if result.skipped_status_mismatch > 0:
            console.print(
                f"  - [yellow]Skipped (status mismatch): "
                f"{result.skipped_status_mismatch}[/yellow]"
            )

        if result.invalid_rows > 0:
            console.print(f"  - [red]Invalid rows: {result.invalid_rows}[/red]")

        if result.errors:
            console.print("[yellow]Errors:[/yellow]")
            for err in result.errors[:10]:
                console.print(f"    - {err}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Import archive decisions error: {e}")
        raise typer.Exit(code=1)


@app.command()
def cross_site_alert_archive_summary(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    resolved_age_days: int = typer.Option(
        30, "--resolved-age-days", help="Minimum age in days for candidates"
    ),
) -> None:
    """Show archive policy summary for cross-site alerts.

    Read-only summary: does not change alert status.
    """
    from marketsentry.cross_site_alert_archive_policy import (
        summarize_cross_site_alert_archive_policy,
    )

    try:
        db_path = database_path or config.database_path

        console.print(
            "[bold blue]Cross-site alert archive policy summary...[/bold blue]"
        )

        summary = summarize_cross_site_alert_archive_policy(
            database_path=db_path,
            resolved_age_days=resolved_age_days,
        )

        console.print(f"\n  Eligible archive candidates: {summary.eligible_candidates}")
        console.print(f"  Already archived: {summary.already_archived}")
        console.print(f"  No-archive marked: {summary.no_archive_marked}")
        console.print(f"  Total resolved: {summary.total_resolved}")
        console.print(f"  Total open: {summary.total_open}")
        console.print(f"  Total acknowledged: {summary.total_acknowledged}")

        if summary.recent_archive_actions > 0:
            console.print(
                f"  Recent archive actions: {summary.recent_archive_actions}"
            )

        if summary.next_actions:
            console.print("\n[bold]Recommended next actions:[/bold]")
            for action in summary.next_actions:
                console.print(f"  - {action}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Archive summary error: {e}")
        raise typer.Exit(code=1)


@app.command()
def snapshot_watchlist(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Create monitoring snapshots for all active watched properties."""
    from marketsentry.monitoring import create_snapshots_for_all_watched

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Creating watchlist monitoring snapshots...[/bold blue]")

        result = create_snapshots_for_all_watched(db_path)

        console.print(f"\n[bold green]SUCCESS:[/bold green] Snapshot run complete")
        console.print(f"  - Watched properties scanned: {result.properties_scanned}")
        console.print(f"  - Snapshots created: {result.snapshots_created}")
        console.print(f"  - Snapshots skipped: {result.snapshots_skipped}")
        console.print(f"  - Changes detected: {result.changes_detected_count}")

        if result.warnings:
            console.print(f"\n[yellow]Warnings ({len(result.warnings)}):[/yellow]")
            for warning in result.warnings[:5]:
                console.print(f"  - {warning}")
            if len(result.warnings) > 5:
                console.print(f"  ... and {len(result.warnings) - 5} more")

        if result.errors:
            console.print(f"\n[red]Errors ({len(result.errors)}):[/red]")
            for error in result.errors[:5]:
                console.print(f"  - {error}")
            if len(result.errors) > 5:
                console.print(f"  ... and {len(result.errors) - 5} more")

        console.print("\n[dim]Run 'marketsentry list-snapshots' to view snapshots[/dim]")
        console.print("[dim]Run 'marketsentry export-watchlist-monitoring-report' to export monitoring report[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Snapshot watchlist error: {e}")
        raise typer.Exit(code=1)


@app.command()
def list_snapshots(
    property_id: Optional[int] = typer.Option(
        None, "--property-id", "-p", help="Filter by property ID"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of snapshots to show"),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """List recent observation snapshots."""
    from marketsentry.database import execute_query

    try:
        db_path = database_path or config.database_path

        # Build query
        if property_id:
            query = """
            SELECT s.snapshot_id, s.property_id, s.snapshot_date, s.price,
                   s.effective_dom, s.listing_status, s.notes,
                   p.address, p.city
            FROM property_observation_snapshots s
            JOIN watched_properties p ON s.property_id = p.property_id
            WHERE s.property_id = ?
            ORDER BY s.snapshot_date DESC
            LIMIT ?
            """
            params = (property_id, limit)
        else:
            query = """
            SELECT s.snapshot_id, s.property_id, s.snapshot_date, s.price,
                   s.effective_dom, s.listing_status, s.notes,
                   p.address, p.city
            FROM property_observation_snapshots s
            JOIN watched_properties p ON s.property_id = p.property_id
            ORDER BY s.snapshot_date DESC
            LIMIT ?
            """
            params = (limit,)

        snapshots = execute_query(query, params, database_path=db_path)

        if not snapshots:
            console.print("[yellow]No snapshots found[/yellow]")
            console.print("\n[dim]Run 'marketsentry snapshot-watchlist' to create snapshots[/dim]")
            return

        # Create table
        title_suffix = f" for property {property_id}" if property_id else ""
        table = Table(title=f"Recent Observation Snapshots{title_suffix}")
        table.add_column("ID", style="cyan")
        table.add_column("Property ID", style="magenta")
        table.add_column("Address")
        table.add_column("Date", style="blue")
        table.add_column("Price", justify="right")
        table.add_column("Effective DOM", justify="right")
        table.add_column("Status")

        for snap in snapshots:
            snap_dict = dict(snap)
            price_str = f"${snap_dict.get('price', 0):,.0f}" if snap_dict.get('price') else "N/A"
            edom_str = str(snap_dict.get('effective_dom')) if snap_dict.get('effective_dom') else "N/A"
            date_str = snap_dict.get('snapshot_date', '')[:10] if snap_dict.get('snapshot_date') else "N/A"

            table.add_row(
                str(snap_dict.get('snapshot_id')),
                str(snap_dict.get('property_id')),
                snap_dict.get('address', 'N/A')[:40],
                date_str,
                price_str,
                edom_str,
                snap_dict.get('listing_status', 'N/A'),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"List snapshots error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_watchlist_monitoring_report(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (default: timestamped file in data/exports/)"
    ),
) -> None:
    """Export watchlist monitoring report to CSV."""
    from marketsentry.monitoring_report import export_watchlist_monitoring_report as export_report

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Exporting watchlist monitoring report...[/bold blue]")

        # Export CSV report
        row_count = export_report(output, db_path)

        console.print(f"\n[bold green]SUCCESS:[/bold green] Report exported")
        console.print(f"  - Properties: {row_count}")

        # Get output path from function if not provided
        if not output:
            from datetime import datetime
            from pathlib import Path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(Path(config.data_exports_dir) / f"watchlist_monitoring_{timestamp}.csv")
        else:
            output_path = output

        console.print(f"  - Output file: {output_path}")

        console.print(
            "\n[dim]Note: This is a watchlist monitoring report, not a purchase recommendation.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export watchlist monitoring report error: {e}")
        raise typer.Exit(code=1)


@app.command()
def import_county_records(
    file: str = typer.Option(..., "--file", "-f", help="Path to county records CSV file"),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Import county records from CSV file."""
    from marketsentry.county_import import import_county_records_csv

    try:
        db_path = database_path or config.database_path

        console.print(f"[bold blue]Importing county records from {file}...[/bold blue]")

        # Import CSV
        result = import_county_records_csv(file, db_path)

        console.print(f"\n[bold green]IMPORT COMPLETE:[/bold green]")
        console.print(f"  - Rows read: {result.total_rows_read}")
        console.print(f"  - Rows inserted: {result.rows_inserted}")
        console.print(f"  - Rows matched: {result.rows_matched}")
        console.print(f"  - Rows unmatched: {result.rows_unmatched}")
        console.print(f"  - Rows rejected: {result.rows_rejected}")

        if result.warnings:
            console.print(f"\n[yellow]WARNINGS ({len(result.warnings)}):[/yellow]")
            for warning in result.warnings[:10]:  # Show first 10
                console.print(f"  - {warning}")
            if len(result.warnings) > 10:
                console.print(f"  ... and {len(result.warnings) - 10} more")

        if result.errors:
            console.print(f"\n[red]ERRORS ({len(result.errors)}):[/red]")
            for error in result.errors[:10]:  # Show first 10
                console.print(f"  - {error}")
            if len(result.errors) > 10:
                console.print(f"  ... and {len(result.errors) - 10} more")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Import county records error: {e}")
        raise typer.Exit(code=1)


@app.command()
def parse_county_fixtures(
    source: str = typer.Option(..., "--source", "-s", help="Source type: assessor, recorder, tax_collector, permit"),
    directory: str = typer.Option(..., "--dir", "-d", help="Directory containing county HTML fixtures"),
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Parse saved county HTML fixtures and store observations."""
    from marketsentry.county_parser import parse_county_record_directory
    from marketsentry.county_import import _insert_county_record
    from pathlib import Path

    try:
        db_path = database_path or config.database_path
        dir_path = Path(directory)

        console.print(f"[bold blue]Parsing county {source} fixtures from {directory}...[/bold blue]")

        # Parse directory
        results = parse_county_record_directory(dir_path, source)

        files_processed = len(results)
        observations_parsed = 0
        observations_inserted = 0
        parse_warnings = 0
        parse_errors = 0

        for result in results:
            if result.parse_status in ["success", "partial"]:
                observations_parsed += 1

                # Insert county record if available
                if result.county_record:
                    if _insert_county_record(result.county_record, db_path):
                        observations_inserted += 1

            parse_warnings += len(result.warnings)
            parse_errors += len(result.errors)

        console.print(f"\n[bold green]PARSE COMPLETE:[/bold green]")
        console.print(f"  - Files processed: {files_processed}")
        console.print(f"  - Observations parsed: {observations_parsed}")
        console.print(f"  - Observations inserted: {observations_inserted}")
        console.print(f"  - Warnings: {parse_warnings}")
        console.print(f"  - Errors: {parse_errors}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Parse county fixtures error: {e}")
        raise typer.Exit(code=1)


@app.command()
def verify_county_records(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Verify county records for watched properties."""
    from marketsentry.county_verification import verify_effective_dom_reset
    from datetime import date, timedelta

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Verifying county records for watched properties...[/bold blue]")

        # Get all active watched properties
        query = "SELECT property_id FROM watched_properties WHERE active_watch_status = 1"
        properties = execute_query(query, database_path=db_path)

        properties_scanned = len(properties)
        transfers_found = 0
        reset_supported_cases = 0

        # Verify each property
        cycle_end = date.today()
        cycle_start = cycle_end - timedelta(days=365 * 5)  # 5 year lookback

        for prop in properties:
            property_id = prop["property_id"]
            verification_result = verify_effective_dom_reset(
                property_id, cycle_start, cycle_end, db_path
            )

            if verification_result.county_transfer_found:
                transfers_found += 1

            if verification_result.county_reset_supported:
                reset_supported_cases += 1

        console.print(f"\n[bold green]VERIFICATION COMPLETE:[/bold green]")
        console.print(f"  - Properties scanned: {properties_scanned}")
        console.print(f"  - County transfers found: {transfers_found}")
        console.print(f"  - Reset-supported cases: {reset_supported_cases}")

        console.print(
            "\n[dim]Note: County transfer records may support Effective DOM reset,"
            " but churn metrics remain preserved separately.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Verify county records error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_county_verification_report(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (default: timestamped file in data/exports/)"
    ),
) -> None:
    """Export county verification report to CSV."""
    from marketsentry.county_verification_report import export_county_verification_report as export_report

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Exporting county verification report...[/bold blue]")

        # Export CSV report
        row_count = export_report(output, db_path)

        console.print(f"\n[bold green]SUCCESS:[/bold green] Report exported")
        console.print(f"  - Properties: {row_count}")

        # Get output path from function if not provided
        if not output:
            from datetime import datetime
            from pathlib import Path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(Path(config.data_exports_dir) / f"county_verification_{timestamp}.csv")
        else:
            output_path = output

        console.print(f"  - Output file: {output_path}")

        console.print(
            "\n[dim]Note: County verification report is for assessment purposes, not a purchase recommendation."
            " Churn Index remains reportable even when county_reset_supported is true.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export county verification report error: {e}")
        raise typer.Exit(code=1)


@app.command()
def recalc_effective_dom_v2(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Recalculate Effective DOM v2 for all watched properties."""
    from marketsentry.effective_dom_v2_recalc import recalc_effective_dom_v2 as recalc_v2

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Recalculating Effective DOM v2 with county reset integration...[/bold blue]")

        # Recalculate v2 metrics
        result = recalc_v2(db_path)

        console.print(f"\n[bold green]RECALCULATION COMPLETE:[/bold green]")
        console.print(f"  - Properties scanned: {result.properties_scanned}")
        console.print(f"  - County transfers considered: {result.county_transfers_considered}")
        console.print(f"  - County resets applied: {result.county_resets_applied}")
        console.print(f"  - Records updated: {result.records_updated}")
        console.print(f"  - Churn metrics preserved: {result.churn_metrics_preserved}")

        if result.warnings:
            console.print(f"\n[yellow]WARNINGS ({len(result.warnings)}):[/yellow]")
            for warning in result.warnings[:10]:
                console.print(f"  - {warning}")
            if len(result.warnings) > 10:
                console.print(f"  ... and {len(result.warnings) - 10} more")

        if result.errors:
            console.print(f"\n[red]ERRORS ({len(result.errors)}):[/red]")
            for error in result.errors[:10]:
                console.print(f"  - {error}")
            if len(result.errors) > 10:
                console.print(f"  ... and {len(result.errors) - 10} more")

        console.print(
            "\n[dim]Note: County reset affects Effective DOM only. Churn Index remains preserved separately.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Recalc effective DOM v2 error: {e}")
        raise typer.Exit(code=1)


@app.command()
def export_effective_dom_v2_report(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (default: timestamped file in data/exports/)"
    ),
) -> None:
    """Export Effective DOM v2 comparison report to CSV."""
    from marketsentry.effective_dom_v2_report import export_effective_dom_v2_report as export_v2_report

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Exporting Effective DOM v2 comparison report...[/bold blue]")

        # Export CSV report
        row_count = export_v2_report(output, db_path)

        console.print(f"\n[bold green]SUCCESS:[/bold green] Report exported")
        console.print(f"  - Properties: {row_count}")

        # Get output path from function if not provided
        if not output:
            from datetime import datetime
            from pathlib import Path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(Path(config.data_exports_dir) / f"effective_dom_v2_{timestamp}.csv")
        else:
            output_path = output

        console.print(f"  - Output file: {output_path}")

        console.print(
            "\n[dim]Note: v1 vs v2 comparison report shows county-verified reset boundaries."
            " Churn Index is preserved separately from Effective DOM reset logic.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Export effective DOM v2 report error: {e}")
        raise typer.Exit(code=1)


@app.command(name="run-initial-review-workflow")
def run_initial_review_workflow_cmd(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    redfin_urls_file: Optional[str] = typer.Option(
        None, "--redfin-urls-file", help="CSV file with Redfin URLs"
    ),
    redfin_search_dir: Optional[str] = typer.Option(
        None, "--redfin-search-dir", help="Directory with Redfin search HTML fixtures"
    ),
    redfin_details_dir: Optional[str] = typer.Option(
        None, "--redfin-details-dir", help="Directory with Redfin detail HTML fixtures"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Directory for output reports"
    ),
) -> None:
    """Run the initial candidate review workflow end-to-end."""
    from marketsentry.workflow import run_initial_review_workflow

    try:
        console.print("[bold blue]Running initial review workflow...[/bold blue]")

        result = run_initial_review_workflow(
            database_path=database_path,
            redfin_urls_file=redfin_urls_file,
            redfin_search_dir=redfin_search_dir,
            redfin_details_dir=redfin_details_dir,
            output_dir=output_dir,
        )

        _print_workflow_result(result)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Initial review workflow error: {e}")
        raise typer.Exit(code=1)


@app.command(name="run-watchlist-refresh-workflow")
def run_watchlist_refresh_workflow_cmd(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    redfin_details_dir: Optional[str] = typer.Option(
        None, "--redfin-details-dir", help="Directory with Redfin detail HTML fixtures"
    ),
    cross_site_root_dir: Optional[str] = typer.Option(
        None, "--cross-site-root-dir", help="Root directory with cross-site fixture subdirectories"
    ),
    county_root_dir: Optional[str] = typer.Option(
        None, "--county-root-dir", help="Root directory with county fixture subdirectories"
    ),
    county_records_file: Optional[str] = typer.Option(
        None, "--county-records-file", help="Path to county records CSV"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Directory for output reports"
    ),
) -> None:
    """Run the watchlist refresh workflow end-to-end."""
    from marketsentry.workflow import run_watchlist_refresh_workflow

    try:
        console.print("[bold blue]Running watchlist refresh workflow...[/bold blue]")

        result = run_watchlist_refresh_workflow(
            database_path=database_path,
            redfin_details_dir=redfin_details_dir,
            cross_site_root_dir=cross_site_root_dir,
            county_root_dir=county_root_dir,
            county_records_file=county_records_file,
            output_dir=output_dir,
        )

        _print_workflow_result(result)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Watchlist refresh workflow error: {e}")
        raise typer.Exit(code=1)


@app.command(name="run-fixture-demo-workflow")
def run_fixture_demo_workflow_cmd(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Demo database path (default: db/demo_marketsentry.db)"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Directory for output reports"
    ),
    reset_demo_db: bool = typer.Option(
        False, "--reset-demo-db", help="Delete existing demo database before starting"
    ),
) -> None:
    """Run a deterministic fixture-based demonstration workflow."""
    from marketsentry.workflow import run_full_fixture_demo_workflow

    try:
        console.print("[bold blue]Running fixture demo workflow...[/bold blue]")

        result = run_full_fixture_demo_workflow(
            database_path=database_path,
            output_dir=output_dir,
            reset_demo_db=reset_demo_db,
        )

        _print_workflow_result(result)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Fixture demo workflow error: {e}")
        raise typer.Exit(code=1)


@app.command(name="workflow-status")
def workflow_status_cmd(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Show workflow status with table counts and latest reports."""
    from marketsentry.workflow import get_workflow_status

    try:
        status = get_workflow_status(database_path)

        console.print(f"\n[bold blue]Database:[/bold blue] {status['database_path']}")
        console.print(f"[bold blue]Exists:[/bold blue] {status['database_exists']}")

        if not status["database_exists"]:
            console.print(
                "\n[yellow]Database not found. Run 'marketsentry init-database' first.[/yellow]"
            )
            return

        # Table counts
        table = Table(title="Table Counts")
        table.add_column("Table", style="cyan")
        table.add_column("Records", justify="right", style="magenta")

        for table_name, count in status["tables"].items():
            table.add_row(table_name, str(count))

        console.print(table)

        # Latest reports
        if status["latest_reports"]:
            console.print("\n[bold blue]Latest Reports:[/bold blue]")
            for report in status["latest_reports"]:
                console.print(f"  - {report['file']}")
                console.print(f"    Modified: {report['modified']}")
        else:
            console.print("\n[dim]No reports found in exports directory.[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Workflow status error: {e}")
        raise typer.Exit(code=1)


def _print_workflow_result(result: "WorkflowRunResult") -> None:
    """Print a workflow result summary to console.

    Args:
        result: The workflow run result to display.
    """
    # Overall status
    failed_steps = [s for s in result.steps if s.status == "failed"]
    if failed_steps:
        console.print(f"\n[bold yellow]WORKFLOW COMPLETED WITH ERRORS[/bold yellow]")
    else:
        console.print(f"\n[bold green]WORKFLOW COMPLETED SUCCESSFULLY[/bold green]")

    console.print(f"  Workflow: {result.workflow_name}")
    if result.duration_seconds is not None:
        console.print(f"  Duration: {result.duration_seconds:.1f}s")

    # Step summary
    table = Table(title="Step Results")
    table.add_column("Step", style="cyan")
    table.add_column("Status")
    table.add_column("Processed", justify="right")
    table.add_column("Created", justify="right")
    table.add_column("Updated", justify="right")

    for step in result.steps:
        status_style = {
            "completed": "[green]completed[/green]",
            "skipped": "[dim]skipped[/dim]",
            "failed": "[red]failed[/red]",
        }.get(step.status, step.status)

        table.add_row(
            step.step_name,
            status_style,
            str(step.records_processed),
            str(step.records_created),
            str(step.records_updated),
        )

    console.print(table)

    # Output files
    if result.output_files:
        console.print("\n[bold blue]Output Files:[/bold blue]")
        for out_file in result.output_files:
            row_str = f" ({out_file.row_count} rows)" if out_file.row_count is not None else ""
            console.print(f"  - [{out_file.report_type}] {out_file.file_path}{row_str}")

    # Summary file
    if result.summary_file:
        console.print(f"\n[bold blue]Summary:[/bold blue] {result.summary_file}")

    # Errors
    if result.errors:
        console.print(f"\n[red]Errors ({len(result.errors)}):[/red]")
        for err in result.errors:
            console.print(f"  - [{err.step_name}] {err.message}")

    # Next action
    if result.next_recommended_action:
        console.print(f"\n[bold]Next recommended action:[/bold]")
        console.print(f"  {result.next_recommended_action}")


@app.command()
def persist_effective_dom_v2(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Persist Effective DOM v2 metrics to watched properties and candidates."""
    from marketsentry.effective_dom_v2_persistence import persist_effective_dom_v2 as persist_v2

    try:
        db_path = database_path or config.database_path

        console.print("[bold blue]Persisting Effective DOM v2 metrics...[/bold blue]")

        # Apply schema migrations first to ensure v2 columns exist
        migrate_schema(db_path)

        # Persist v2 metrics
        result = persist_v2(db_path)

        console.print(f"\n[bold green]PERSIST COMPLETE:[/bold green]")
        console.print(f"  - Properties scanned: {result.properties_scanned}")
        console.print(f"  - County transfers considered: {result.county_transfers_considered}")
        console.print(f"  - County resets applied: {result.county_resets_applied}")
        console.print(f"  - Records updated: {result.records_updated}")
        console.print(f"  - Churn metrics preserved: {result.churn_metrics_preserved}")

        if result.warnings:
            console.print(f"\n[yellow]WARNINGS ({len(result.warnings)}):[/yellow]")
            for warning in result.warnings[:10]:
                console.print(f"  - {warning}")
            if len(result.warnings) > 10:
                console.print(f"  ... and {len(result.warnings) - 10} more")

        if result.errors:
            console.print(f"\n[red]ERRORS ({len(result.errors)}):[/red]")
            for error in result.errors[:10]:
                console.print(f"  - {error}")
            if len(result.errors) > 10:
                console.print(f"  ... and {len(result.errors) - 10} more")

        console.print(
            "\n[dim]Note: County reset affects Effective DOM only. "
            "Churn Index remains preserved separately.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Persist effective DOM v2 error: {e}")
        raise typer.Exit(code=1)


@app.command(name="automation-status")
def automation_status_cmd() -> None:
    """Print automation environment status for scheduled task setup."""
    from marketsentry.automation import get_automation_status

    try:
        status = get_automation_status()

        console.print("\n[bold blue]Market_Sentry Automation Status[/bold blue]")
        console.print(f"  Project Root:      {status.project_root}")
        console.print(f"  Python Executable: {status.python_executable}")
        console.print(
            f"  Virtualenv:        {status.virtualenv_path or 'Not detected'}"
        )
        console.print(f"  Database Path:     {status.database_path}")
        console.print(f"  Exports Directory: {status.exports_directory}")
        console.print(f"  Scheduled Logs:    {status.scheduled_logs_directory}")
        console.print(f"  Scripts Directory: {status.scripts_directory}")

        # Script status
        if status.scripts_found:
            scripts_table = Table(title="Task Scheduler Scripts")
            scripts_table.add_column("Script", style="cyan")
            scripts_table.add_column("Status")

            for script in status.scripts_found:
                scripts_table.add_row(script, "[green]found[/green]")
            for script in status.scripts_missing:
                scripts_table.add_row(script, "[red]missing[/red]")

            console.print(scripts_table)
        else:
            console.print("\n[yellow]No scripts found in scripts/ directory.[/yellow]")

        # Latest scheduled log
        if status.latest_scheduled_log:
            console.print(f"\n[bold blue]Latest Scheduled Log:[/bold blue]")
            console.print(f"  {status.latest_scheduled_log}")
            if status.latest_scheduled_log_preview:
                console.print(f"\n[dim]{status.latest_scheduled_log_preview}[/dim]")
        else:
            console.print("\n[dim]No scheduled logs found.[/dim]")

        console.print(
            "\n[dim]Scheduled tasks run local workflows only. "
            "No live scraping or network calls.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Automation status error: {e}")
        raise typer.Exit(code=1)


@app.command(name="write-scheduler-scripts")
def write_scheduler_scripts_cmd() -> None:
    """Validate that expected scheduler scripts exist and print paths."""
    from marketsentry.automation import validate_scripts_exist, get_project_root

    try:
        root = get_project_root()
        scripts_dir = root / "scripts"
        results = validate_scripts_exist(root)

        console.print("\n[bold blue]Market_Sentry Scheduler Scripts[/bold blue]")
        console.print(f"  Scripts Directory: {scripts_dir}\n")

        all_found = True
        for script_name, exists in results.items():
            if exists:
                script_path = scripts_dir / script_name
                console.print(f"  [green]OK[/green]  {script_path}")
            else:
                console.print(f"  [red]MISSING[/red]  {scripts_dir / script_name}")
                all_found = False

        if all_found:
            console.print(
                "\n[bold green]All expected scripts are present.[/bold green]"
            )
            console.print(
                "\n[dim]To install weekly watchlist refresh task:[/dim]"
            )
            console.print(
                f"  powershell -ExecutionPolicy Bypass -File "
                f'"{scripts_dir / "install_task_scheduler_watchlist_refresh.ps1"}"'
            )
        else:
            console.print(
                "\n[bold yellow]Some scripts are missing.[/bold yellow]"
            )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Write scheduler scripts error: {e}")
        raise typer.Exit(code=1)


@app.command(name="launch-dashboard")
def launch_dashboard_cmd(
    db: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    exports_dir: Optional[str] = typer.Option(
        None, "--exports-dir", help="Exports directory (default: from config)"
    ),
    port: int = typer.Option(
        8501, "--port", help="Port for Streamlit server"
    ),
) -> None:
    """Launch the local review dashboard in a browser.

    Starts a Streamlit app that reads local database and CSV reports only.
    No network calls or scraping.
    """
    import subprocess
    import sys

    app_path = Path(__file__).parent / "dashboard_app.py"

    if not app_path.exists():
        console.print(f"[bold red]Error:[/bold red] Dashboard app not found at {app_path}")
        raise typer.Exit(code=1)

    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--server.port", str(port),
        "--server.headless", "false",
    ]

    console.print(f"[bold blue]Launching dashboard...[/bold blue]")
    console.print(f"  App: {app_path}")
    console.print(f"  Port: {port}")
    console.print(f"  URL: http://localhost:{port}")
    console.print(f"\n[dim]Press Ctrl+C to stop the dashboard.[/dim]")

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        console.print(
            "\n[bold red]Error:[/bold red] Streamlit is not installed."
        )
        console.print("Install it with: pip install streamlit")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n[bold blue]Dashboard stopped.[/bold blue]")
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error:[/bold red] Dashboard exited with code {e.returncode}")
        raise typer.Exit(code=1)


@app.command(name="dashboard-summary")
def dashboard_summary_cmd(
    database_path: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Print ASCII-safe dashboard summary without launching browser UI."""
    from marketsentry.dashboard import get_dashboard_summary

    try:
        summary = get_dashboard_summary(database_path)

        console.print(f"\n[bold blue]Market_Sentry Dashboard Summary[/bold blue]")
        console.print(f"  Database: {summary.database_path}")
        console.print(f"  Exists: {summary.database_exists}")

        if not summary.database_exists:
            console.print(
                "\n[yellow]Database not found. Run 'marketsentry init-database' first.[/yellow]"
            )
            return

        # Table counts
        table = Table(title="Database Counts")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="magenta")

        table.add_row("Candidates in Review Queue", str(summary.candidates_total))
        table.add_row("Watched Properties (Total)", str(summary.watched_total))
        table.add_row("Watched Properties (Active)", str(summary.watched_active))
        table.add_row("High Priority Watched", str(summary.high_priority_watched))
        table.add_row("Observation Snapshots", str(summary.snapshots_total))
        table.add_row("Cross-Site Observations", str(summary.cross_site_observations))
        table.add_row("County Records", str(summary.county_records))
        table.add_row("Listing Events", str(summary.listing_events))

        console.print(table)

        # Analytics
        analytics = Table(title="Analytics")
        analytics.add_column("Metric", style="cyan")
        analytics.add_column("Count", justify="right", style="magenta")

        analytics.add_row("Quiet Gatekeeper Failures", str(summary.quiet_gatekeeper_failures))
        analytics.add_row("Strong Review Candidates", str(summary.strong_review_candidates))
        analytics.add_row("County Reset Applied", str(summary.county_reset_applied_count))
        analytics.add_row("High Churn (>= 6.0)", str(summary.high_churn_count))
        analytics.add_row("Reports in Manifest", str(summary.reports_in_manifest))

        console.print(analytics)

        console.print(
            "\n[dim]This is an analytical summary, not a purchase recommendation.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Dashboard summary error: {e}")
        raise typer.Exit(code=1)


@app.command(name="source-adapters")
def source_adapters_cmd() -> None:
    """Print registered source adapters and their supported modes."""
    from marketsentry.source_adapters.registry import get_registry

    try:
        registry = get_registry()
        adapters = registry.list_adapters()

        console.print("\n[bold blue]Market_Sentry Source Adapters[/bold blue]\n")

        table = Table(title="Registered Adapters")
        table.add_column("Source", style="cyan")
        table.add_column("Display Name")
        table.add_column("Current Mode")
        table.add_column("Supported Modes")
        table.add_column("Search")
        table.add_column("Detail")
        table.add_column("Notes")

        for adapter in adapters:
            modes = ", ".join(m.value for m in adapter.get_supported_modes())
            table.add_row(
                adapter.source_name,
                adapter.display_name,
                adapter.current_mode.value,
                modes,
                "yes" if adapter.config.supports_search else "no",
                "yes" if adapter.config.supports_property_detail else "no",
                adapter.config.notes[:50] if adapter.config.notes else "",
            )

        console.print(table)
        console.print(
            f"\n[dim]Total adapters: {len(adapters)}. "
            "Live retrieval is disabled by default.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="retrieval-compliance-status")
def retrieval_compliance_status_cmd() -> None:
    """Print retrieval compliance configuration status."""
    from marketsentry.source_adapters.compliance import get_compliance_status

    try:
        status = get_compliance_status()

        console.print("\n[bold blue]Retrieval Compliance Status[/bold blue]\n")

        table = Table(title="Compliance Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value")

        enabled = status["live_retrieval_globally_enabled"]
        enabled_str = (
            "[red]ENABLED[/red]" if enabled else "[green]disabled (safe)[/green]"
        )
        table.add_row("Live retrieval globally enabled", enabled_str)

        sources = status["allowed_live_sources"]
        sources_str = ", ".join(sources) if sources else "(none)"
        table.add_row("Allowed live sources", sources_str)

        ua = status["user_agent_configured"]
        table.add_row(
            "User-Agent configured",
            "[green]yes[/green]" if ua else "[yellow]no[/yellow]",
        )
        table.add_row("User-Agent", str(status["user_agent"]))

        contact = status["contact_email_configured"]
        table.add_row(
            "Contact email configured",
            "[green]yes[/green]" if contact else "[yellow]no[/yellow]",
        )
        table.add_row("Contact email", str(status["contact_email"]))

        table.add_row(
            "Max requests per minute", str(status["max_requests_per_minute"])
        )

        dry_run = status["dry_run_required_before_live"]
        table.add_row(
            "Dry-run required before live",
            "[green]yes[/green]" if dry_run else "[yellow]no[/yellow]",
        )

        table.add_row("Retrieval audit directory", str(status["retrieval_audit_dir"]))

        console.print(table)

        # Warnings
        warnings = status.get("warnings", [])
        if warnings:
            console.print("\n[bold yellow]Warnings:[/bold yellow]")
            for warning in warnings:
                console.print(f"  - {warning}")

        # Overall status
        blocked = status["live_retrieval_blocked"]
        if blocked:
            console.print(
                "\n[bold green]Live retrieval is BLOCKED (safe default).[/bold green]"
            )
        else:
            potentially = status["live_retrieval_potentially_allowed"]
            if potentially:
                console.print(
                    "\n[bold red]Live retrieval is POTENTIALLY ALLOWED. "
                    "Use with caution.[/bold red]"
                )
            else:
                console.print(
                    "\n[bold yellow]Live retrieval is enabled but missing "
                    "required configuration.[/bold yellow]"
                )

        console.print(
            "\n[dim]No network calls are performed by this command.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="dry-run-redfin-search")
def dry_run_redfin_search_cmd(
    url: str = typer.Option(
        ..., "--url", help="Redfin search URL to preview"
    ),
    db: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", help="Output file path (optional)"
    ),
) -> None:
    """Dry-run preview for a Redfin search page retrieval.

    Validates the URL and shows what would be retrieved without
    making any network calls.
    """
    from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

    try:
        adapter = RedfinAdapter()
        result = adapter.dry_run_search(url)

        console.print("\n[bold blue]Redfin Search Dry-Run Preview[/bold blue]\n")

        if result.blocked:
            console.print(f"[bold red]BLOCKED:[/bold red] {result.block_reason}")
        else:
            console.print(result.dry_run_preview)

        if result.compliance_warnings:
            console.print("\n[bold yellow]Compliance Warnings:[/bold yellow]")
            for warning in result.compliance_warnings:
                console.print(f"  - {warning}")

        console.print(
            "\n[dim]No network call was performed. "
            "network_call_performed=False[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="dry-run-redfin-property")
def dry_run_redfin_property_cmd(
    url: str = typer.Option(
        ..., "--url", help="Redfin property URL to preview"
    ),
    db: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", help="Output file path (optional)"
    ),
) -> None:
    """Dry-run preview for a Redfin property detail page retrieval.

    Validates the URL and shows what would be retrieved without
    making any network calls.
    """
    from marketsentry.source_adapters.redfin_adapter import RedfinAdapter

    try:
        adapter = RedfinAdapter()
        result = adapter.dry_run_property_detail(url)

        console.print("\n[bold blue]Redfin Property Detail Dry-Run Preview[/bold blue]\n")

        if result.blocked:
            console.print(f"[bold red]BLOCKED:[/bold red] {result.block_reason}")
        else:
            console.print(result.dry_run_preview)

        if result.compliance_warnings:
            console.print("\n[bold yellow]Compliance Warnings:[/bold yellow]")
            for warning in result.compliance_warnings:
                console.print(f"  - {warning}")

        console.print(
            "\n[dim]No network call was performed. "
            "network_call_performed=False[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="retrieval-policy-check")
def retrieval_policy_check_cmd(
    source: str = typer.Option(
        "redfin", "--source", help="Source adapter name (e.g., redfin)"
    ),
    url: str = typer.Option(
        ..., "--url", help="URL to check policy for"
    ),
    request_type: str = typer.Option(
        "property_detail", "--request-type", help="Request type (search, property_detail)"
    ),
    mode: str = typer.Option(
        "live_http", "--mode", help="Retrieval mode to check (live_http, dry_run, etc.)"
    ),
) -> None:
    """Check retrieval policy for a URL. No network calls performed."""
    from marketsentry.source_adapters.policy import evaluate_retrieval_policy

    try:
        policy = evaluate_retrieval_policy(
            source_name=source,
            url=url,
            request_type=request_type,
            retrieval_mode=mode,
        )

        console.print("\n[bold blue]Retrieval Policy Check[/bold blue]\n")

        table = Table(title="Policy Decision")
        table.add_column("Field", style="cyan")
        table.add_column("Value")

        decision_style = (
            "[green]" if policy.decision.value == "allowed"
            else "[red]" if policy.is_blocked
            else "[yellow]"
        )
        table.add_row("Decision", f"{decision_style}{policy.decision.value}[/]")
        table.add_row("Source", policy.source_name)
        table.add_row("URL", policy.url[:80])
        table.add_row("Request Type", policy.request_type)
        table.add_row("Mode", policy.retrieval_mode)
        table.add_row("Compliance Passed", str(policy.compliance_passed))
        table.add_row("Robots Passed", str(policy.robots_passed))
        table.add_row("Robots Unknown", str(policy.robots_unknown))
        table.add_row("Rate Limit Passed", str(policy.rate_limit_passed))
        table.add_row("Dry-Run Approved", str(policy.dry_run_approved))
        table.add_row("Fixture Capture Recommended", str(policy.fixture_capture_recommended))

        if policy.suggested_fixture_path:
            table.add_row("Suggested Fixture Path", policy.suggested_fixture_path)

        console.print(table)

        if policy.reasons:
            console.print("\n[bold]Reasons:[/bold]")
            for reason in policy.reasons:
                severity_style = {
                    "error": "[red]",
                    "warning": "[yellow]",
                    "info": "[dim]",
                }.get(reason.severity, "")
                console.print(
                    f"  {severity_style}[{reason.severity}][/] {reason.message}"
                )

        console.print(
            "\n[dim]No network calls performed. network_call_performed=False[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="list-fixture-capture-queue")
def list_fixture_capture_queue_cmd(
    db: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    source: Optional[str] = typer.Option(
        None, "--source", help="Filter by source site"
    ),
) -> None:
    """List pending fixture capture requests."""
    from marketsentry.fixture_capture_queue import (
        get_capture_request_count,
        list_pending_capture_requests,
    )

    try:
        requests = list_pending_capture_requests(
            source_site=source, database_path=db
        )

        console.print("\n[bold blue]Fixture Capture Queue (Pending)[/bold blue]\n")

        if not requests:
            console.print("[dim]No pending capture requests.[/dim]")
            return

        table = Table(title=f"Pending Capture Requests ({len(requests)})")
        table.add_column("ID", style="cyan", justify="right")
        table.add_column("Source")
        table.add_column("URL")
        table.add_column("Type")
        table.add_column("Suggested Path")
        table.add_column("Priority", justify="right")
        table.add_column("Created")

        for req in requests:
            url_display = req.get("source_url", "")
            if len(url_display) > 60:
                url_display = url_display[:57] + "..."
            table.add_row(
                str(req.get("capture_request_id", "")),
                req.get("source_site", ""),
                url_display,
                req.get("request_type", ""),
                req.get("suggested_fixture_path", ""),
                str(req.get("priority", "")),
                str(req.get("created_at", ""))[:19],
            )

        console.print(table)

        total = get_capture_request_count(database_path=db)
        pending = get_capture_request_count(status="pending", database_path=db)
        console.print(f"\n[dim]Total: {total} | Pending: {pending}[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="export-fixture-capture-queue")
def export_fixture_capture_queue_cmd(
    db: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Output directory (default: data/exports)"
    ),
) -> None:
    """Export fixture capture queue to CSV."""
    from marketsentry.fixture_capture_queue import export_capture_queue_csv

    try:
        output_path = export_capture_queue_csv(
            output_dir=output_dir, database_path=db
        )
        console.print(
            f"\n[bold green]Fixture capture queue exported to:[/bold green] {output_path}"
        )
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="mark-fixture-captured")
def mark_fixture_captured_cmd(
    capture_request_id: int = typer.Option(
        ..., "--capture-request-id", help="Capture request ID to mark"
    ),
    fixture_path: Optional[str] = typer.Option(
        None, "--fixture-path", help="Path to the captured fixture file"
    ),
    db: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
) -> None:
    """Mark a fixture capture request as captured."""
    from marketsentry.fixture_capture_queue import mark_fixture_captured

    try:
        updated = mark_fixture_captured(
            capture_request_id=capture_request_id,
            fixture_path=fixture_path,
            database_path=db,
        )
        if updated:
            console.print(
                f"\n[bold green]Capture request {capture_request_id} marked as captured.[/bold green]"
            )
            if fixture_path:
                console.print(f"  Fixture path: {fixture_path}")
        else:
            console.print(
                f"\n[bold yellow]Capture request {capture_request_id} not found.[/bold yellow]"
            )
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="retrieve-redfin-search")
def retrieve_redfin_search_cmd(
    url: str = typer.Option(
        ..., "--url", help="Redfin search URL to retrieve"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Output directory for saved fixture"
    ),
    db: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    force_live: bool = typer.Option(
        False, "--force-live", help="Attempt live HTTP retrieval (requires full config)"
    ),
    dry_run_only: bool = typer.Option(
        False, "--dry-run-only", help="Perform dry-run preview only"
    ),
) -> None:
    """Retrieve a Redfin search page via HTTP or preview in dry-run mode.

    Live retrieval is disabled by default and requires explicit opt-in
    via environment variables and --force-live flag. No browser automation.
    """
    from marketsentry.source_adapters.redfin_adapter import RedfinAdapter
    from marketsentry.source_adapters.http_client import StandardLibraryHttpClient

    try:
        adapter = RedfinAdapter()

        if dry_run_only:
            result = adapter.dry_run_search(url)
            console.print("\n[bold blue]Redfin Search Dry-Run Preview[/bold blue]\n")
            if result.blocked:
                console.print(f"[bold red]BLOCKED:[/bold red] {result.block_reason}")
            else:
                console.print(result.dry_run_preview)
            if result.compliance_warnings:
                console.print("\n[bold yellow]Compliance Warnings:[/bold yellow]")
                for warning in result.compliance_warnings:
                    console.print(f"  - {warning}")
            console.print(
                "\n[dim]No network call was performed. "
                "network_call_performed=False[/dim]"
            )
            return

        if not force_live:
            console.print("\n[bold yellow]Live retrieval requires --force-live flag.[/bold yellow]")
            console.print(
                "\nLive HTTP retrieval is disabled by default. To attempt live retrieval:\n"
                "  1. Set MARKETSENTRY_LIVE_RETRIEVAL_ENABLED=true\n"
                "  2. Set MARKETSENTRY_ALLOWED_LIVE_SOURCES=redfin\n"
                "  3. Set MARKETSENTRY_LIVE_USER_AGENT=MarketSentry/1.0\n"
                "  4. Set MARKETSENTRY_LIVE_CONTACT_EMAIL=your@email.com\n"
                "  5. Save robots.txt to data/policies/robots/redfin_robots.txt\n"
                "  6. Run dry-run-redfin-search first\n"
                "  7. Pass --force-live to this command\n"
            )
            console.print("[dim]Use --dry-run-only to preview without network calls.[/dim]")
            return

        # Attempt live retrieval with real HTTP client
        http_client = StandardLibraryHttpClient()
        result = adapter.retrieve_search(url, http_client=http_client)

        console.print("\n[bold blue]Redfin Search Live Retrieval[/bold blue]\n")

        if result.blocked:
            console.print(f"[bold red]BLOCKED:[/bold red] {result.block_reason}")
            console.print(f"  network_call_performed: {result.network_call_performed}")
            console.print(
                "\n[dim]A fixture capture request has been created. "
                "Run 'marketsentry list-fixture-capture-queue' to see pending requests.[/dim]"
            )
        elif result.success:
            console.print("[bold green]SUCCESS:[/bold green] Live retrieval completed.")
            console.print(f"  Fixture saved: {result.fixture_path}")
            console.print(f"  network_call_performed: {result.network_call_performed}")
            console.print(
                "\n[dim]Parse the saved fixture with existing fixture parsers.[/dim]"
            )
        else:
            console.print(f"[bold red]FAILED:[/bold red] {result.error_message}")
            console.print(f"  network_call_performed: {result.network_call_performed}")

        console.print(f"\n[dim]Audit log: logs/retrieval_audit/[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="retrieve-redfin-property")
def retrieve_redfin_property_cmd(
    url: str = typer.Option(
        ..., "--url", help="Redfin property detail URL to retrieve"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Output directory for saved fixture"
    ),
    db: Optional[str] = typer.Option(
        None, "--db", help="Database path (default: from config)"
    ),
    force_live: bool = typer.Option(
        False, "--force-live", help="Attempt live HTTP retrieval (requires full config)"
    ),
    dry_run_only: bool = typer.Option(
        False, "--dry-run-only", help="Perform dry-run preview only"
    ),
) -> None:
    """Retrieve a Redfin property detail page via HTTP or preview in dry-run mode.

    Live retrieval is disabled by default and requires explicit opt-in
    via environment variables and --force-live flag. No browser automation.
    """
    from marketsentry.source_adapters.redfin_adapter import RedfinAdapter
    from marketsentry.source_adapters.http_client import StandardLibraryHttpClient

    try:
        adapter = RedfinAdapter()

        if dry_run_only:
            result = adapter.dry_run_property_detail(url)
            console.print("\n[bold blue]Redfin Property Detail Dry-Run Preview[/bold blue]\n")
            if result.blocked:
                console.print(f"[bold red]BLOCKED:[/bold red] {result.block_reason}")
            else:
                console.print(result.dry_run_preview)
            if result.compliance_warnings:
                console.print("\n[bold yellow]Compliance Warnings:[/bold yellow]")
                for warning in result.compliance_warnings:
                    console.print(f"  - {warning}")
            console.print(
                "\n[dim]No network call was performed. "
                "network_call_performed=False[/dim]"
            )
            return

        if not force_live:
            console.print("\n[bold yellow]Live retrieval requires --force-live flag.[/bold yellow]")
            console.print(
                "\nLive HTTP retrieval is disabled by default. To attempt live retrieval:\n"
                "  1. Set MARKETSENTRY_LIVE_RETRIEVAL_ENABLED=true\n"
                "  2. Set MARKETSENTRY_ALLOWED_LIVE_SOURCES=redfin\n"
                "  3. Set MARKETSENTRY_LIVE_USER_AGENT=MarketSentry/1.0\n"
                "  4. Set MARKETSENTRY_LIVE_CONTACT_EMAIL=your@email.com\n"
                "  5. Save robots.txt to data/policies/robots/redfin_robots.txt\n"
                "  6. Run dry-run-redfin-property first\n"
                "  7. Pass --force-live to this command\n"
            )
            console.print("[dim]Use --dry-run-only to preview without network calls.[/dim]")
            return

        # Attempt live retrieval with real HTTP client
        http_client = StandardLibraryHttpClient()
        result = adapter.retrieve_property_detail(url, http_client=http_client)

        console.print("\n[bold blue]Redfin Property Detail Live Retrieval[/bold blue]\n")

        if result.blocked:
            console.print(f"[bold red]BLOCKED:[/bold red] {result.block_reason}")
            console.print(f"  network_call_performed: {result.network_call_performed}")
            console.print(
                "\n[dim]A fixture capture request has been created. "
                "Run 'marketsentry list-fixture-capture-queue' to see pending requests.[/dim]"
            )
        elif result.success:
            console.print("[bold green]SUCCESS:[/bold green] Live retrieval completed.")
            console.print(f"  Fixture saved: {result.fixture_path}")
            console.print(f"  network_call_performed: {result.network_call_performed}")
            console.print(
                "\n[dim]Parse the saved fixture with existing fixture parsers.[/dim]"
            )
        else:
            console.print(f"[bold red]FAILED:[/bold red] {result.error_message}")
            console.print(f"  network_call_performed: {result.network_call_performed}")

        console.print(f"\n[dim]Audit log: logs/retrieval_audit/[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="retrieval-audit-report")
def retrieval_audit_report_cmd(
    audit_dir: Optional[str] = typer.Option(
        None, "--audit-dir", help="Audit log directory (default: logs/retrieval_audit)"
    ),
) -> None:
    """Summarize retrieval audit logs."""
    from marketsentry.source_adapters.audit_report import generate_audit_report

    try:
        report = generate_audit_report(audit_dir=audit_dir)

        console.print("\n[bold blue]Retrieval Audit Report[/bold blue]\n")

        table = Table(title="Audit Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="magenta")

        table.add_row("Total Decisions", str(report["total_decisions"]))
        table.add_row("Allowed", str(report["allowed_count"]))
        table.add_row("Blocked", str(report["blocked_count"]))
        table.add_row("Dry-Runs", str(report["dry_run_count"]))
        table.add_row("Live Attempts", str(report["live_attempt_count"]))
        table.add_row("Network Calls (True)", str(report["network_call_true_count"]))
        table.add_row("Network Calls (False)", str(report["network_call_false_count"]))
        table.add_row("Files Scanned", str(report["files_scanned"]))

        console.print(table)

        # Sources breakdown
        sources = report.get("sources", {})
        if sources:
            src_table = Table(title="By Source")
            src_table.add_column("Source", style="cyan")
            src_table.add_column("Count", justify="right")
            for src, count in sorted(sources.items()):
                src_table.add_row(src, str(count))
            console.print(src_table)

        # Modes breakdown
        modes = report.get("modes", {})
        if modes:
            mode_table = Table(title="By Mode")
            mode_table.add_column("Mode", style="cyan")
            mode_table.add_column("Count", justify="right")
            for mode, count in sorted(modes.items()):
                mode_table.add_row(mode, str(count))
            console.print(mode_table)

        # Blocked reasons
        blocked_reasons = report.get("blocked_reasons", {})
        if blocked_reasons:
            console.print("\n[bold]Blocked Reasons:[/bold]")
            for reason, count in sorted(blocked_reasons.items(), key=lambda x: -x[1]):
                reason_display = reason[:100] if len(reason) > 100 else reason
                console.print(f"  [{count}x] {reason_display}")

        console.print(
            "\n[dim]No network calls are performed by this command.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="process-redfin-retrieved-fixtures")
def process_redfin_retrieved_fixtures_cmd(
    db: Optional[str] = typer.Option(
        None, "--db", help="Database path"
    ),
    search_dir: Optional[str] = typer.Option(
        None, "--search-dir", help="Redfin search fixtures directory"
    ),
    details_dir: Optional[str] = typer.Option(
        None, "--details-dir", help="Redfin detail fixtures directory"
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Output directory for reports"
    ),
    force_reprocess: bool = typer.Option(
        False, "--force-reprocess", help="Reprocess even if content hash matches"
    ),
) -> None:
    """Process retrieved Redfin fixtures through the local parsing pipeline.

    Parses search and detail fixtures, inserts/enriches candidates,
    recalculates metrics, exports reports. No live retrieval.
    """
    from marketsentry.retrieved_fixture_processor import (
        process_redfin_retrieved_fixtures,
    )

    try:
        result = process_redfin_retrieved_fixtures(
            search_dir=search_dir,
            details_dir=details_dir,
            database_path=db,
            output_dir=output_dir,
            force_reprocess=force_reprocess,
        )

        console.print("\n[bold blue]Redfin Retrieved Fixture Processing[/bold blue]\n")

        table = Table(title="Processing Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="magenta")

        table.add_row("Search files scanned", str(result.search_files_scanned))
        table.add_row("Search files processed", str(result.search_files_processed))
        table.add_row("Detail files scanned", str(result.detail_files_scanned))
        table.add_row("Detail files processed", str(result.detail_files_processed))
        table.add_row("Candidates discovered", str(result.total_candidates_discovered))
        table.add_row("Candidates inserted", str(result.total_candidates_inserted))
        table.add_row("Duplicates skipped", str(result.total_duplicates_skipped))
        table.add_row("Candidates enriched", str(result.total_candidates_enriched))
        table.add_row("Listing events inserted", str(result.total_listing_events_inserted))
        table.add_row("Reports exported", str(len(result.reports_exported)))
        table.add_row("Capture queue marked", str(result.capture_queue_items_marked))

        console.print(table)

        if result.reports_exported:
            console.print("\n[bold]Reports:[/bold]")
            for rpt in result.reports_exported:
                console.print(f"  {rpt}")

        console.print(f"\nManifest: {result.manifest_path}")

        if result.warnings:
            console.print(f"\n[bold yellow]Warnings ({len(result.warnings)}):[/bold yellow]")
            for w in result.warnings[:10]:
                console.print(f"  - {w}")

        if result.errors:
            console.print(f"\n[bold red]Errors ({len(result.errors)}):[/bold red]")
            for e in result.errors[:10]:
                console.print(f"  - {e}")

        console.print(
            "\n[dim]No live retrieval was performed. "
            "Processing uses local fixtures only.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="process-redfin-search-fixtures")
def process_redfin_search_fixtures_cmd(
    db: Optional[str] = typer.Option(
        None, "--db", help="Database path"
    ),
    search_dir: Optional[str] = typer.Option(
        None, "--search-dir", help="Redfin search fixtures directory"
    ),
    force_reprocess: bool = typer.Option(
        False, "--force-reprocess", help="Reprocess even if content hash matches"
    ),
) -> None:
    """Process Redfin search fixtures only. No live retrieval."""
    from marketsentry.retrieved_fixture_processor import (
        process_redfin_search_fixtures,
    )

    try:
        result = process_redfin_search_fixtures(
            search_dir=search_dir,
            database_path=db,
            force_reprocess=force_reprocess,
        )

        console.print("\n[bold blue]Redfin Search Fixture Processing[/bold blue]\n")
        console.print(f"  Files scanned: {result.search_files_scanned}")
        console.print(f"  Files processed: {result.search_files_processed}")
        console.print(f"  Candidates discovered: {result.total_candidates_discovered}")
        console.print(f"  Candidates inserted: {result.total_candidates_inserted}")
        console.print(f"  Duplicates skipped: {result.total_duplicates_skipped}")
        console.print(f"\n  Manifest: {result.manifest_path}")

        if result.warnings:
            console.print(f"\n[bold yellow]Warnings:[/bold yellow]")
            for w in result.warnings[:5]:
                console.print(f"  - {w}")

        console.print(
            "\n[dim]No live retrieval was performed.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="process-redfin-detail-fixtures")
def process_redfin_detail_fixtures_cmd(
    db: Optional[str] = typer.Option(
        None, "--db", help="Database path"
    ),
    details_dir: Optional[str] = typer.Option(
        None, "--details-dir", help="Redfin detail fixtures directory"
    ),
    force_reprocess: bool = typer.Option(
        False, "--force-reprocess", help="Reprocess even if content hash matches"
    ),
) -> None:
    """Process Redfin detail fixtures only. No live retrieval."""
    from marketsentry.retrieved_fixture_processor import (
        process_redfin_detail_fixtures,
    )

    try:
        result = process_redfin_detail_fixtures(
            details_dir=details_dir,
            database_path=db,
            force_reprocess=force_reprocess,
        )

        console.print("\n[bold blue]Redfin Detail Fixture Processing[/bold blue]\n")
        console.print(f"  Files scanned: {result.detail_files_scanned}")
        console.print(f"  Files processed: {result.detail_files_processed}")
        console.print(f"  Candidates enriched: {result.total_candidates_enriched}")
        console.print(f"  Listing events inserted: {result.total_listing_events_inserted}")
        console.print(f"\n  Manifest: {result.manifest_path}")

        if result.warnings:
            console.print(f"\n[bold yellow]Warnings:[/bold yellow]")
            for w in result.warnings[:5]:
                console.print(f"  - {w}")

        console.print(
            "\n[dim]No live retrieval was performed.[/dim]"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="retrieve-and-process-redfin-property")
def retrieve_and_process_redfin_property_cmd(
    url: str = typer.Option(
        ..., "--url", help="Redfin property detail URL"
    ),
    db: Optional[str] = typer.Option(
        None, "--db", help="Database path"
    ),
    force_live: bool = typer.Option(
        False, "--force-live", help="Attempt live HTTP retrieval"
    ),
    dry_run_only: bool = typer.Option(
        False, "--dry-run-only", help="Dry-run only, no retrieval"
    ),
) -> None:
    """Retrieve a Redfin property page and immediately process the fixture.

    If live retrieval succeeds, the saved fixture is parsed and the
    candidate is enriched. If blocked, a capture queue request is added.
    No browser automation. All M16 guardrails apply.
    """
    from marketsentry.source_adapters.redfin_adapter import RedfinAdapter
    from marketsentry.source_adapters.http_client import StandardLibraryHttpClient
    from marketsentry.retrieved_fixture_processor import (
        process_redfin_detail_fixtures,
    )

    try:
        adapter = RedfinAdapter()

        if dry_run_only:
            result = adapter.dry_run_property_detail(url)
            console.print("\n[bold blue]Dry-Run Preview[/bold blue]\n")
            if result.blocked:
                console.print(f"[bold red]BLOCKED:[/bold red] {result.block_reason}")
            else:
                console.print(result.dry_run_preview)
            console.print("\n[dim]network_call_performed=False[/dim]")
            return

        if not force_live:
            console.print("\n[bold yellow]Live retrieval requires --force-live flag.[/bold yellow]")
            console.print(
                "\nSee 'marketsentry retrieve-redfin-property --help' for details.\n"
                "Use --dry-run-only to preview without network calls."
            )
            return

        # Attempt live retrieval
        http_client = StandardLibraryHttpClient()
        result = adapter.retrieve_property_detail(url, http_client=http_client)

        if result.blocked:
            console.print(f"\n[bold red]BLOCKED:[/bold red] {result.block_reason}")
            console.print(f"  network_call_performed: {result.network_call_performed}")
            console.print(
                "\n[dim]Run 'marketsentry list-fixture-capture-queue' to see pending requests.[/dim]"
            )
            return

        if not result.success or not result.fixture_path:
            console.print(f"\n[bold red]FAILED:[/bold red] {result.error_message}")
            return

        console.print(f"\n[bold green]Retrieved:[/bold green] {result.fixture_path}")

        # Process the saved fixture
        from pathlib import Path

        fixture_dir = str(Path(result.fixture_path).parent)
        proc_result = process_redfin_detail_fixtures(
            details_dir=fixture_dir,
            database_path=db,
            force_reprocess=True,
        )

        console.print(f"  Candidates enriched: {proc_result.total_candidates_enriched}")
        console.print(f"  Listing events inserted: {proc_result.total_listing_events_inserted}")
        console.print("\n[dim]Processing complete. No additional network calls.[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Milestone 18 - Redfin Pending Capture Batch Retrieval
# ---------------------------------------------------------------------------


@app.command(name="dry-run-pending-redfin-fixtures")
def dry_run_pending_redfin_fixtures_cmd(
    max_items: int = typer.Option(0, "--max-items", help="Max items to evaluate (0=all)"),
    request_type: Optional[str] = typer.Option(None, "--request-type", help="Filter: search or property_detail"),
    db: Optional[str] = typer.Option(None, "--db", help="Database path"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Output directory"),
) -> None:
    """Dry-run preview of pending Redfin fixture capture requests.

    Evaluates pending capture queue items against policy checks.
    No network calls are performed. Queue items remain pending.
    """
    from marketsentry.redfin_batch_retrieval import (
        BatchRetrievalConfig,
        retrieve_pending_redfin_capture_batch,
        summarize_batch_retrieval_run,
    )

    console = Console()
    console.print("[bold]Dry-Run Pending Redfin Fixture Capture Requests[/bold]\n")

    try:
        config = BatchRetrievalConfig(
            mode="dry_run_only",
            max_items=max_items,
            request_type_filter=request_type,
            force_live=False,
            database_path=db,
            output_dir=output_dir,
        )

        result = retrieve_pending_redfin_capture_batch(config=config)
        summary = summarize_batch_retrieval_run(result)
        console.print(summary)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="retrieve-pending-redfin-fixtures")
def retrieve_pending_redfin_fixtures_cmd(
    max_items: int = typer.Option(0, "--max-items", help="Max items to retrieve (0=all)"),
    request_type: Optional[str] = typer.Option(None, "--request-type", help="Filter: search or property_detail"),
    db: Optional[str] = typer.Option(None, "--db", help="Database path"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Output directory"),
    force_live: bool = typer.Option(False, "--force-live", help="Attempt live HTTP retrieval (requires full config)"),
    process_after_retrieval: bool = typer.Option(False, "--process-after-retrieval", help="Process fixtures after retrieval"),
    dry_run_only: bool = typer.Option(False, "--dry-run-only", help="Perform dry-run preview only"),
) -> None:
    """Retrieve pending Redfin fixture capture requests.

    By default, no retrieval occurs without --force-live.
    Use --dry-run-only for preview mode.
    Use --process-after-retrieval to process fixtures after batch completion.

    No scheduled script should call this command by default.
    """
    from marketsentry.redfin_batch_retrieval import (
        BatchRetrievalConfig,
        retrieve_pending_redfin_capture_batch,
        summarize_batch_retrieval_run,
    )

    console = Console()
    console.print("[bold]Retrieve Pending Redfin Fixture Capture Requests[/bold]\n")

    if dry_run_only:
        mode = "dry_run_only"
    elif process_after_retrieval:
        mode = "retrieve_and_process"
    else:
        mode = "retrieve_only"

    if not force_live and not dry_run_only:
        console.print(
            "[bold yellow]BLOCKED:[/bold yellow] Live retrieval requires --force-live flag.\n"
            "\n"
            "Without --force-live, no network calls are performed.\n"
            "Use --dry-run-only to preview pending items.\n"
            "Use --force-live to attempt live retrieval (requires full config).\n"
            "\n"
            "All retrieval policy checks (compliance, robots, rate limit, dry-run\n"
            "approval) are enforced per item even with --force-live.\n"
        )
        raise typer.Exit(code=0)

    try:
        config = BatchRetrievalConfig(
            mode=mode,
            max_items=max_items,
            request_type_filter=request_type,
            force_live=force_live,
            database_path=db,
            output_dir=output_dir,
        )

        result = retrieve_pending_redfin_capture_batch(config=config)
        summary = summarize_batch_retrieval_run(result)
        console.print(summary)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Milestone 19: Redfin Batch Retrieval Approval Workflow
# ---------------------------------------------------------------------------


@app.command()
def prepare_redfin_retrieval_approval(
    max_items: int = typer.Option(0, "--max-items", help="Maximum items to include. 0 for no limit."),
    request_type: Optional[str] = typer.Option(None, "--request-type", help="Filter by request type (search, property_detail)."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to database file."),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Output directory for approval files."),
) -> None:
    """Prepare a batch approval package for pending Redfin capture requests.

    Dry-runs all pending Redfin capture queue items and writes an approval CSV
    with approved_for_live=false. The user edits the CSV to approve selected
    items, then runs retrieve-approved-redfin-batch to retrieve them.

    No network calls are performed by this command.
    """
    from marketsentry.retrieval_approval import (
        prepare_redfin_batch_approval_package,
        summarize_approval_package,
    )

    try:
        package = prepare_redfin_batch_approval_package(
            max_items=max_items,
            request_type=request_type,
            database_path=db,
            output_dir=output_dir,
        )
        summary = summarize_approval_package(package)
        console.print(summary)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def retrieve_approved_redfin_batch(
    approval_file: str = typer.Option(..., "--approval-file", help="Path to the user-edited approval CSV file."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to database file."),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Output directory for reports."),
    force_live: bool = typer.Option(False, "--force-live", help="Enable live retrieval (required for network calls)."),
    process_after_retrieval: bool = typer.Option(False, "--process-after-retrieval", help="Process fixtures after retrieval."),
    dry_run_only: bool = typer.Option(False, "--dry-run-only", help="Validate and preview only, no retrieval."),
) -> None:
    """Retrieve only approved items from a batch approval CSV.

    Loads the user-edited approval CSV, validates rows against the current
    capture queue, and retrieves only items with approved_for_live=true.

    Without --force-live, no network calls are performed.
    With --dry-run-only, the command validates and previews only.
    """
    from marketsentry.retrieval_approval import (
        retrieve_approved_redfin_batch as _retrieve_approved,
        summarize_approved_retrieval_run,
    )

    if not force_live and not dry_run_only:
        console.print(
            "[bold yellow]BLOCKED:[/bold yellow] Approved retrieval requires --force-live flag.\n"
            "\n"
            "Without --force-live, no network calls are performed.\n"
            "Use --dry-run-only to validate and preview the approval CSV.\n"
            "Use --force-live to retrieve approved items (requires full config).\n"
            "\n"
            "All retrieval policy checks (compliance, robots, rate limit, dry-run\n"
            "approval) are enforced per item even with --force-live.\n"
        )
        raise typer.Exit(code=0)

    try:
        result = _retrieve_approved(
            approval_csv_path=approval_file,
            force_live=force_live,
            dry_run_only=dry_run_only,
            process_after_retrieval=process_after_retrieval,
            database_path=db,
            output_dir=output_dir,
        )
        summary = summarize_approved_retrieval_run(result)
        console.print(summary)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Milestone 20: Retrieval Operations Dashboard CLI
# ---------------------------------------------------------------------------


@app.command()
def retrieval_operations_summary(
    db: Optional[str] = typer.Option(None, "--db", help="Path to database file."),
    audit_dir: Optional[str] = typer.Option(None, "--audit-dir", help="Path to audit log directory."),
    processed_dir: Optional[str] = typer.Option(None, "--processed-dir", help="Path to processed data directory."),
) -> None:
    """Show a summary of retrieval operations.

    Displays counts for capture queue, approval packages, batch retrieval
    runs, audit decisions, safety configuration, and latest files.
    Read-only. No network calls.
    """
    from marketsentry.retrieval_dashboard import (
        format_retrieval_operations_summary,
        get_retrieval_operations_summary,
    )

    try:
        summary = get_retrieval_operations_summary(
            database_path=db,
            audit_dir=audit_dir,
            processed_dir=processed_dir,
        )
        output = format_retrieval_operations_summary(summary)
        console.print(output)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def export_retrieval_operations_report(
    db: Optional[str] = typer.Option(None, "--db", help="Path to database file."),
    audit_dir: Optional[str] = typer.Option(None, "--audit-dir", help="Path to audit log directory."),
    processed_dir: Optional[str] = typer.Option(None, "--processed-dir", help="Path to processed data directory."),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Output directory for the report."),
    report_format: str = typer.Option("md", "--format", help="Report format: md or csv."),
) -> None:
    """Export a retrieval operations report to a file.

    Exports a summary plus key tables as a Markdown or CSV report.
    Read-only. No network calls.
    """
    from marketsentry.retrieval_dashboard import (
        export_retrieval_operations_report as _export_report,
    )

    try:
        report_path = _export_report(
            database_path=db,
            audit_dir=audit_dir,
            processed_dir=processed_dir,
            output_dir=output_dir,
            report_format=report_format,
        )
        console.print(f"Report exported to: {report_path}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Milestone 21: Retrieval Health Checks CLI
# ---------------------------------------------------------------------------


@app.command()
def retrieval_health_check(
    db: Optional[str] = typer.Option(None, "--db", help="Path to database file."),
    audit_dir: Optional[str] = typer.Option(None, "--audit-dir", help="Path to audit log directory."),
    processed_dir: Optional[str] = typer.Option(None, "--processed-dir", help="Path to processed data directory."),
    raw_dir: Optional[str] = typer.Option(None, "--raw-dir", help="Path to raw data directory."),
) -> None:
    """Run retrieval health checks and display results.

    Checks for stale capture requests, stale approval packages, unprocessed
    fixtures, missing policy files, audit anomalies, and repeated blocks.
    Read-only. No network calls.
    """
    from marketsentry.retrieval_health import (
        format_retrieval_health_summary,
        run_retrieval_health_checks,
    )

    try:
        summary = run_retrieval_health_checks(
            database_path=db,
            audit_dir=audit_dir,
            processed_dir=processed_dir,
            raw_dir=raw_dir,
        )
        output = format_retrieval_health_summary(summary)
        console.print(output)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def export_retrieval_health_report(
    db: Optional[str] = typer.Option(None, "--db", help="Path to database file."),
    audit_dir: Optional[str] = typer.Option(None, "--audit-dir", help="Path to audit log directory."),
    processed_dir: Optional[str] = typer.Option(None, "--processed-dir", help="Path to processed data directory."),
    raw_dir: Optional[str] = typer.Option(None, "--raw-dir", help="Path to raw data directory."),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Output directory for the report."),
    report_format: str = typer.Option("md", "--format", help="Report format: md or csv."),
) -> None:
    """Export a retrieval health report to a file.

    Runs all health checks and exports issues and next actions as a
    Markdown or CSV report. Read-only. No network calls.
    """
    from marketsentry.retrieval_health import (
        export_retrieval_health_report as _export_report,
    )

    try:
        report_path = _export_report(
            database_path=db,
            audit_dir=audit_dir,
            processed_dir=processed_dir,
            raw_dir=raw_dir,
            output_dir=output_dir,
            report_format=report_format,
        )
        console.print(f"Health report exported to: {report_path}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Milestone 22: Cross-Site Adapter Parity CLI
# ---------------------------------------------------------------------------


@app.command()
def dry_run_cross_site_property(
    source: str = typer.Option(..., "--source", help="Source site (zillow, realtor, homes, compass)."),
    url: str = typer.Option(..., "--url", help="Property URL to dry-run."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to database file."),
    output: Optional[str] = typer.Option(None, "--output", help="Output directory."),
) -> None:
    """Dry-run preview for a cross-site property URL.

    Validates the URL, infers request type, creates a fixture capture queue
    request, and shows a dry-run preview. No network calls.
    """
    from marketsentry.source_adapters.base import RetrievalRequest

    source_lower = source.lower()
    valid_sources = ["zillow", "realtor", "homes", "compass"]
    if source_lower not in valid_sources:
        console.print(
            f"[bold red]Error:[/bold red] Unknown source '{source}'. "
            f"Valid sources: {', '.join(valid_sources)}"
        )
        raise typer.Exit(code=1)

    try:
        if source_lower == "zillow":
            from marketsentry.source_adapters.zillow_adapter import ZillowAdapter
            adapter = ZillowAdapter()
        elif source_lower == "realtor":
            from marketsentry.source_adapters.realtor_adapter import RealtorAdapter
            adapter = RealtorAdapter()
        elif source_lower == "homes":
            from marketsentry.source_adapters.homes_adapter import HomesAdapter
            adapter = HomesAdapter()
        else:
            from marketsentry.source_adapters.compass_adapter import CompassAdapter
            adapter = CompassAdapter()

        request = RetrievalRequest(
            source_name=source_lower,
            url=url,
        )

        result = adapter.dry_run(request)

        if result.blocked:
            console.print(f"[bold yellow]BLOCKED:[/bold yellow] {result.block_reason}")
        else:
            console.print(result.dry_run_preview)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def process_cross_site_fixtures(
    root_dir: Optional[str] = typer.Option(None, "--root-dir", help="Root data directory."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to database file."),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Output directory for manifest."),
    force_reprocess: bool = typer.Option(False, "--force-reprocess", help="Reprocess even if unchanged."),
) -> None:
    """Process all cross-site fixtures from all supported sources.

    Scans Zillow, Realtor.com, Homes.com, and Compass fixture directories,
    parses HTML files, inserts observations, writes manifest. No network calls.
    """
    from marketsentry.cross_site_fixture_processor import (
        format_cross_site_processing_summary,
        process_cross_site_fixtures as _process,
    )

    try:
        run = _process(
            root_dir=root_dir,
            database_path=db,
            output_dir=output_dir,
            force_reprocess=force_reprocess,
        )
        summary = format_cross_site_processing_summary(run)
        console.print(summary)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def process_cross_site_source_fixtures(
    source: str = typer.Option(..., "--source", help="Source site (zillow, realtor, homes, compass)."),
    dir: Optional[str] = typer.Option(None, "--dir", help="Directory containing fixtures."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to database file."),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Output directory for manifest."),
    force_reprocess: bool = typer.Option(False, "--force-reprocess", help="Reprocess even if unchanged."),
) -> None:
    """Process cross-site fixtures for a single source.

    Scans the specified source fixture directory, parses HTML files,
    inserts observations, writes manifest. No network calls.
    """
    from marketsentry.cross_site_fixture_processor import (
        format_cross_site_processing_summary,
        process_cross_site_source_fixtures as _process_source,
    )

    source_lower = source.lower()
    valid_sources = ["zillow", "realtor", "homes", "compass"]
    if source_lower not in valid_sources:
        console.print(
            f"[bold red]Error:[/bold red] Unknown source '{source}'. "
            f"Valid sources: {', '.join(valid_sources)}"
        )
        raise typer.Exit(code=1)

    try:
        run = _process_source(
            source_site=source_lower,
            fixture_dir=dir,
            database_path=db,
            output_dir=output_dir,
            force_reprocess=force_reprocess,
        )
        summary = format_cross_site_processing_summary(run)
        console.print(summary)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
