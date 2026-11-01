from pipeline.scraper.dedup import deduplicate
from pipeline.scraper.geocode import fill_locations_offline, fill_missing_names
from pipeline.scraper.loader import slugify, upsert_values
from pipeline.scraper.sources.base import RawPark
from pipeline.scraper.sources.osm_overpass import (
    build_query,
    classify_environment,
    classify_type,
    element_to_park,
    is_park,
)
from pipeline.scraper.world import split_tile, unique_by_source_id, world_tiles


def element(tags, type_="way", id_=1):
    return {"type": type_, "id": id_, "center": {"lat": 29.9, "lon": -95.4}, "tags": tags}


def park(name="Test Park", lat=29.9, lng=-95.4, source_id="osm-way-1", **kwargs):
    return RawPark(name=name, lat=lat, lng=lng, source="osm", source_id=source_id, **kwargs)


def test_real_houston_shops_are_rejected():
    select_skate_shop = {"name": "Select Skate Shop", "shop": "sports", "sport": "skateboard"}
    geometric = {"name": "Geometric", "shop": "sports", "sport": "skateboard"}
    assert element_to_park(element(select_skate_shop, "node")) is None
    assert element_to_park(element(geometric, "node")) is None


def test_real_houston_park_is_kept():
    result = element_to_park(element({"leisure": "pitch", "name": "North Houston Skate Park", "sport": "skateboard"}))
    assert result.name == "North Houston Skate Park"
    assert result.source_id == "osm-way-1"


def test_shop_named_park_without_shop_tag_is_rejected():
    assert not is_park({"name": "Downtown Skate Shop", "sport": "skateboard"})


def test_description_is_never_used_as_name():
    result = element_to_park(element({"leisure": "skatepark", "description": "Concrete bowl by the river"}))
    assert result.name == ""


def test_relation_center_is_used():
    result = element_to_park(element({"leisure": "skatepark", "name": "X"}, "relation"))
    assert (result.lat, result.lng) == (29.9, -95.4)


def test_element_without_coordinates_is_skipped():
    assert element_to_park({"type": "way", "id": 1, "tags": {"leisure": "skatepark"}}) is None


def test_type_needs_evidence():
    assert classify_type({"name": "Clinton Skatepark"}) is None
    assert classify_type({"name": "Riverton Beverly Skatepark"}) is None
    assert classify_type({"name": "Main Street Skatepark"}) is None
    assert classify_type({"name": "Hillside DIY"}) == "diy"
    assert classify_type({"name": "Burnside Bowl"}) == "transition"


def test_environment():
    assert classify_environment({"name": "Clinton"}) == "outdoor"
    assert classify_environment({"indoor": "yes"}) == "indoor"
    assert classify_environment({"building": "yes"}) == "indoor"
    assert classify_environment({"name": "Indoor and outdoor park"}) == "both"


def test_query_targets_parks_and_excludes_shops():
    query = build_query((1, 2, 3, 4))
    assert '"shop"!~"."' in query and "(1,2,3,4)" in query and "nwr" in query


def test_dedup_merges_similar_names_nearby():
    a = park("Jamail Skatepark", source_id="a", city="Houston")
    b = park("Jamail Skate Park", lat=29.9005, source_id="b")
    assert [p.source_id for p in deduplicate([b, a])] == ["a"]


def test_dedup_keeps_different_parks_nearby():
    assert len(deduplicate([park("Alpha", source_id="a"), park("Zebra Plaza", lat=29.9005, source_id="b")])) == 2


def test_dedup_keeps_same_name_far_apart():
    assert len(deduplicate([park("Central", source_id="a"), park("Central", lat=40.0, source_id="b")])) == 2


def test_dedup_absorbs_unnamed_into_named_neighbor():
    kept = deduplicate([park("", source_id="unnamed"), park("Real Park", lat=29.9005, source_id="named")])
    assert [p.source_id for p in kept] == ["named"]


def test_dedup_matches_across_grid_cells():
    a = park("Border", lat=29.9999, source_id="a")
    b = park("Border", lat=30.0001, source_id="b")
    assert len(deduplicate([a, b])) == 1


def test_dedup_handles_large_input_quickly():
    parks = [park(f"P{i}", lat=(i % 170) - 85, lng=(i % 350) - 175 + i * 0.0001, source_id=str(i)) for i in range(30000)]
    assert len(deduplicate(parks)) > 0


def test_offline_location_works_worldwide():
    parks = fill_locations_offline([
        park(lat=48.85, lng=2.35, source_id="paris"),
        park(lat=29.76, lng=-95.37, source_id="houston"),
    ])
    assert (parks[0].country, parks[0].city) == ("FR", "Paris")
    assert (parks[1].country, parks[1].state) == ("US", "TX")


def test_existing_tags_win_over_offline_city():
    parks = fill_locations_offline([park(lat=29.76, lng=-95.37, city="Bellaire")])
    assert parks[0].city == "Bellaire"


def test_missing_names_are_filled():
    named = fill_missing_names([park("", city="Paris"), park("", city=None), park("Kept")])
    assert [p.name for p in named] == ["Skatepark in Paris", "Skatepark", "Kept"]


def test_slug_keeps_unique_suffix_when_truncated():
    long_a = slugify("x" * 400, None, "a")
    long_b = slugify("x" * 400, None, "b")
    assert long_a != long_b and len(long_a) <= 255


def test_oversized_values_are_clipped():
    values = upsert_values(park("n" * 400, zip_code="z" * 50, surface="s" * 100, city="c" * 200))
    assert len(values[0]) == 255 and len(values[4]) == 128 and len(values[7]) == 16 and len(values[13]) == 64


def test_world_tiles_cover_the_globe():
    tiles = world_tiles()
    assert min(t[1] for t in tiles) == -180 and max(t[3] for t in tiles) == 180
    assert max(t[2] for t in tiles) == 84


def test_split_tile_covers_original():
    parts = split_tile((0, 0, 30, 30))
    assert len(parts) == 4 and (0, 0, 15.0, 15.0) in parts and (15.0, 15.0, 30, 30) in parts


def test_border_duplicates_are_removed_by_source_id():
    assert len(unique_by_source_id([park(source_id="same"), park(source_id="same")])) == 1


def test_cli_exposes_scrape_subcommand():
    from typer.testing import CliRunner

    from pipeline.scraper.main import app

    result = CliRunner().invoke(app, ["scrape", "--help"])
    assert result.exit_code == 0 and "--world" in result.output


def test_named_parks_score_above_generated_names():
    from pipeline.scraper.loader import compute_quality_score

    assert compute_quality_score(park("Real Park")) > compute_quality_score(park("Skatepark in Paris"))
