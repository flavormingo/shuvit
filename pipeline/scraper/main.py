#!/usr/bin/env python3
"""Shuvit skatepark data pipeline CLI."""

import asyncio
import logging

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from pipeline.scraper.dedup import deduplicate
from pipeline.scraper.geocode import reverse_geocode_parks
from pipeline.scraper.loader import load_parks
from pipeline.scraper.sources.google_places import GooglePlacesSource
from pipeline.scraper.sources.osm_overpass import OverpassSource

app = typer.Typer(help="Shuvit skatepark data pipeline")
console = Console()

# Houston bounding boxes for thorough coverage
HOUSTON_BBOX = (29.5, -95.8, 30.1, -95.0)


def setup_logging(verbose: bool = False):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@app.command()
def scrape(
    source: str = typer.Option("osm", help="Source: osm, google, all"),
    bbox: str = typer.Option(None, help="Bounding box: south,west,north,east"),
    database_url: str = typer.Option(None, envvar="DATABASE_URL"),
    dry_run: bool = typer.Option(False, help="Fetch and dedup only, don't load"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
):
    """Scrape skatepark data and load into database."""
    setup_logging(verbose)
    asyncio.run(_scrape(source, bbox, database_url, dry_run))


async def _scrape(
    source: str,
    bbox_str: str | None,
    database_url: str | None,
    dry_run: bool,
):
    bbox = HOUSTON_BBOX
    if bbox_str:
        parts = [float(x.strip()) for x in bbox_str.split(",")]
        if len(parts) != 4:
            console.print("[red]bbox must be: south,west,north,east[/red]")
            raise typer.Exit(1)
        bbox = tuple(parts)

    all_parks = []

    with console.status("Fetching skateparks..."):
        if source in ("osm", "all"):
            osm = OverpassSource()
            parks = await osm.fetch(bbox)
            console.print(f"  OSM: [green]{len(parks)}[/green] parks found")
            all_parks.extend(parks)

        if source in ("google", "all"):
            gp = GooglePlacesSource()
            parks = await gp.fetch(bbox)
            console.print(f"  Google Places: [green]{len(parks)}[/green] parks found")
            all_parks.extend(parks)

    if not all_parks:
        console.print("[yellow]No skateparks found.[/yellow]")
        return

    # Deduplicate
    with console.status("Deduplicating..."):
        deduped = deduplicate(all_parks)

    # Reverse geocode to fill in addresses
    console.print("Reverse geocoding addresses (1 req/sec for Nominatim)...")
    deduped = await reverse_geocode_parks(deduped)

    # Display results
    table = Table(title=f"Skateparks Found ({len(deduped)})")
    table.add_column("Name", style="bold")
    table.add_column("Address")
    table.add_column("City")
    table.add_column("Type")

    for park in deduped[:30]:
        table.add_row(
            park.name,
            park.address or "",
            f"{park.city or ''}, {park.state or ''}".strip(", "),
            park.park_type or "unknown",
        )

    if len(deduped) > 30:
        table.add_row("...", f"(+{len(deduped) - 30} more)", "", "")

    console.print(table)

    if dry_run:
        console.print("[yellow]Dry run — skipping database load.[/yellow]")
        return

    # Load into database
    with console.status("Loading into database..."):
        count = await load_parks(deduped, database_url)

    console.print(f"[green]Successfully loaded {count} skateparks.[/green]")


@app.command()
def houston(
    database_url: str = typer.Option(None, envvar="DATABASE_URL"),
    dry_run: bool = typer.Option(False, help="Fetch only, don't load"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
):
    """Scrape all Houston, TX skateparks (convenience command)."""
    setup_logging(verbose)
    console.print("[bold]Scraping Houston, TX skateparks...[/bold]")
    asyncio.run(_scrape("all", None, database_url, dry_run))


if __name__ == "__main__":
    app()
