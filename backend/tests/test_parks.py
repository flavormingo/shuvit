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


async def test_bounds_includes_only_parks_in_viewport(client, park_id):
    inside = await client.get("/parks/bounds", params={"south": 29, "west": -96, "north": 30, "east": -95})
    assert [p["id"] for p in inside.json()] == [park_id]
    outside = await client.get("/parks/bounds", params={"south": 40, "west": -75, "north": 41, "east": -73})
    assert outside.json() == []


async def test_bounds_handles_antimeridian(client, park_id):
    # west > east means the box wraps around the far side of the world through Houston's side.
    wrapped = await client.get("/parks/bounds", params={"south": 29, "west": 170, "north": 30, "east": -95})
    assert [p["id"] for p in wrapped.json()] == [park_id]
    missed = await client.get("/parks/bounds", params={"south": 29, "west": 170, "north": 30, "east": -100})
    assert missed.json() == []
