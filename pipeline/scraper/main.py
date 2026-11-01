#!/usr/bin/env python3
import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from pipeline.scraper.dedup import deduplicate
from pipeline.scraper.geocode import (
    fill_locations_offline,
    fill_missing_names,
    reverse_geocode_parks,
)
from pipeline.scraper.loader import load_parks
from pipeline.scraper.sources.google_places import GooglePlacesSource
from pipeline.scraper.sources.osm_overpass import HOUSTON_BBOX, OverpassSource
from pipeline.scraper.world import WorldFetcher

app = typer.Typer(help="Shuvit skatepark data pipeline")
console = Console()


@app.callback()
def main():
    """Shuvit skatepark data pipeline."""


def setup_logging(verbose: bool = False):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def parse_bbox(bbox: str | None) -> tuple[float, float, float, float]:
    if not bbox:
        return HOUSTON_BBOX
    parts = [float(value.strip()) for value in bbox.split(",")]
    if len(parts) != 4:
        console.print("[red]bbox must be: south,west,north,east[/red]")
        raise typer.Exit(1)
    return tuple(parts)


@app.command()
def scrape(
    source: str = typer.Option("osm", help="Source: osm, google, all"),
    bbox: str = typer.Option(None, help="Bounding box: south,west,north,east"),
    world: bool = typer.Option(False, help="Fetch OSM parks for the whole world"),
    geocoder: str = typer.Option("offline", help="offline, or nominatim for small areas only"),
    cache_dir: Path = typer.Option(Path("/tmp/shuvit-tiles"), help="Resumable tile cache for --world"),
    database_url: str = typer.Option(None, envvar="DATABASE_URL"),
    dry_run: bool = typer.Option(False, help="Fetch and dedup only, don't load"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
):
    """Scrape skatepark data and load it into the database."""
    setup_logging(verbose)
    asyncio.run(_scrape(source, parse_bbox(bbox), world, geocoder, cache_dir, database_url, dry_run))


async def _scrape(source, bbox, world, geocoder, cache_dir, database_url, dry_run):
    all_parks = []

    if source in ("osm", "all"):
        if world:
            fetcher = WorldFetcher(cache_dir)
            parks = await fetcher.fetch()
            if fetcher.failed_tiles:
                console.print(f"[red]Failed tiles, rerun to retry: {fetcher.failed_tiles}[/red]")
        else:
            parks = await OverpassSource().fetch(bbox)
        console.print(f"OSM: {len(parks)} parks found")
        all_parks.extend(parks)

    if source in ("google", "all"):
        parks = await GooglePlacesSource().fetch(bbox)
        console.print(f"Google Places: {len(parks)} parks found")
        all_parks.extend(parks)

    if not all_parks:
        console.print("[yellow]No skateparks found.[/yellow]")
        return

    deduped = deduplicate(all_parks)

    if geocoder == "nominatim":
        deduped = await reverse_geocode_parks(deduped)
    else:
        deduped = fill_locations_offline(deduped)
    deduped = fill_missing_names(deduped)

    print_summary(deduped)

    if dry_run:
        console.print("[yellow]Dry run: skipping database load.[/yellow]")
        return

    count = await load_parks(deduped, database_url)
    console.print(f"[green]Loaded {count} skateparks.[/green]")


def print_summary(parks):
    table = Table(title=f"Skateparks Found ({len(parks)})")
    table.add_column("Name", style="bold")
    table.add_column("Place")
    table.add_column("Country")
    table.add_column("Type")
    for park in parks[:30]:
        table.add_row(
            park.name,
            ", ".join(part for part in (park.city, park.state) if part),
            park.country,
            park.park_type or "unknown",
        )
    if len(parks) > 30:
        table.add_row("...", f"(+{len(parks) - 30} more)", "", "")
    console.print(table)


if __name__ == "__main__":
    app()
