from sqlalchemy import text

from app.database import async_session


async def test_near_finds_park_within_radius(client, park_id):
    near = await client.get("/parks/near", params={"lat": 29.76, "lng": -95.37, "radius_km": 5})
    assert [p["id"] for p in near.json()] == [park_id]
    far = await client.get("/parks/near", params={"lat": 40.7, "lng": -74.0, "radius_km": 5})
    assert far.json() == []


async def test_search_and_detail(client, park_id):
    assert [p["id"] for p in (await client.get("/parks", params={"q": "test"})).json()] == [park_id]
    detail = await client.get(f"/parks/{park_id}")
    assert detail.json()["name"] == "Test Park" and detail.json()["media"] == []


async def test_favorites_add_list_remove(client, login, park_id):
    headers = await login("a@example.com")
    assert (await client.post("/favorites", json={"park_id": park_id}, headers=headers)).status_code == 201
    assert (await client.post("/favorites", json={"park_id": park_id}, headers=headers)).status_code == 409
    listed = (await client.get("/favorites", headers=headers)).json()
    assert listed[0]["park"]["name"] == "Test Park"
    assert (await client.delete(f"/favorites/{park_id}", headers=headers)).status_code == 204
    assert (await client.get("/favorites", headers=headers)).json() == []


async def test_display_name_rules(client, login):
    alice = await login("alice@example.com")
    bob = await login("bob@example.com")
    assert (await client.patch("/user/me", json={"display_name": "Alice1"}, headers=alice)).status_code == 200
    assert (await client.patch("/user/me", json={"display_name": "ALICE1"}, headers=bob)).status_code == 409
    assert (await client.patch("/user/me", json={"display_name": "no spaces"}, headers=bob)).status_code == 400


async def add_park(name, lat, lng, city=None, environment=None, is_free=True):
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO skateparks (name, slug, geom, city, environment, is_free) VALUES "
                "(:name, :slug, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), :city, :environment, :is_free)"
            ),
            {
                "name": name,
                "slug": f"{name}-{lat}-{lng}",
                "lat": lat,
                "lng": lng,
                "city": city,
                "environment": environment,
                "is_free": is_free,
            },
        )
        await session.commit()


WORLD = {"south": -85, "west": -180, "north": 85, "east": 180}


async def test_map_groups_nearby_parks_and_returns_singles(client):
    await add_park("A", 10.1, 10.1)
    await add_park("B", 10.2, 10.2)
    await add_park("C", 50.0, 50.0)

    body = (await client.get("/parks/map", params={**WORLD, "cell": 45})).json()
    assert [c["count"] for c in body["clusters"]] == [2]
    cluster = body["clusters"][0]
    assert cluster["south"] == 10.1 and cluster["north"] == 10.2
    assert cluster["lat"] == 10.15 or abs(cluster["lat"] - 10.15) < 1e-9
    assert [p["name"] for p in body["parks"]] == ["C"]


async def test_map_splits_clusters_when_zoomed_in(client):
    await add_park("A", 10.1, 10.1)
    await add_park("B", 10.2, 10.2)
    body = (await client.get("/parks/map", params={"south": 10, "west": 10, "north": 11, "east": 11, "cell": 0.05})).json()
    assert body["clusters"] == []
    assert sorted(p["name"] for p in body["parks"]) == ["A", "B"]


async def test_map_excludes_parks_outside_viewport(client):
    await add_park("A", 10.1, 10.1)
    body = (await client.get("/parks/map", params={"south": 40, "west": -75, "north": 41, "east": -73, "cell": 0.1})).json()
    assert body == {"clusters": [], "parks": []}


async def test_map_caps_cell_count_for_tiny_cell_on_wide_view(client):
    await add_park("A", 10.1, 10.1)
    await add_park("B", 10.2, 10.2)
    body = (await client.get("/parks/map", params={**WORLD, "cell": 0.0001})).json()
    assert [c["count"] for c in body["clusters"]] == [2]


async def test_map_handles_antimeridian(client):
    await add_park("East", 0.5, 179.5)
    await add_park("West", 0.5, -179.5)
    await add_park("Elsewhere", 0.5, 0.0)
    body = (await client.get("/parks/map", params={"south": 0, "west": 179, "north": 1, "east": -179, "cell": 0.1})).json()
    assert sorted(p["name"] for p in body["parks"]) == ["East", "West"]


async def test_map_filters(client):
    await add_park("Inside", 10.1, 10.1, environment="indoor", is_free=False)
    await add_park("Outside", 50.0, 50.0, environment="outdoor")
    params = {**WORLD, "cell": 45}
    indoor = (await client.get("/parks/map", params={**params, "environment": "indoor"})).json()
    assert [p["name"] for p in indoor["parks"]] == ["Inside"]
    free = (await client.get("/parks/map", params={**params, "is_free": "true"})).json()
    assert [p["name"] for p in free["parks"]] == ["Outside"]
    assert (await client.get("/parks/map", params={**params, "environment": "nope"})).status_code == 422


async def test_search_finds_city_and_ranks_real_names_first(client):
    await add_park("Skatepark in Paris", 48.8, 2.3, city="Paris")
    await add_park("Bercy Bowl", 48.84, 2.38, city="Paris")
    await add_park("Paris Plaza", 48.85, 2.35, city="Paris")
    await add_park("Elsewhere", 10.0, 10.0, city="Lyon")
    names = [p["name"] for p in (await client.get("/parks", params={"q": "paris"})).json()]
    assert names == ["Paris Plaza", "Bercy Bowl", "Skatepark in Paris"]


async def test_search_treats_wildcards_literally(client):
    await add_park("Alpha", 10.0, 10.0)
    await add_park("100% Skate", 20.0, 20.0)
    assert [p["name"] for p in (await client.get("/parks", params={"q": "%"})).json()] == ["100% Skate"]
    assert (await client.get("/parks", params={"q": "_"})).json() == []
