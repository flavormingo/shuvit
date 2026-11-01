import io
import shutil
import subprocess

import piexif
import pillow_heif
import pytest
from PIL import Image


def jpeg_with_gps() -> bytes:
    gps = {piexif.GPSIFD.GPSLatitudeRef: b"N", piexif.GPSIFD.GPSLatitude: ((29, 1), (45, 1), (0, 1))}
    exif = piexif.dump({"0th": {piexif.ImageIFD.Orientation: 6}, "GPS": gps})
    output = io.BytesIO()
    Image.new("RGB", (800, 400), "red").save(output, "JPEG", exif=exif)
    return output.getvalue()


def heic_bytes() -> bytes:
    output = io.BytesIO()
    pillow_heif.from_pillow(Image.new("RGB", (800, 600), "blue")).save(output, format="HEIF")
    return output.getvalue()


def png_with_alpha() -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(output, "PNG")
    return output.getvalue()


async def upload(client, park_id, headers, data, name="upload.jpg", mime="image/jpeg", **fields):
    return await client.post(
        f"/parks/{park_id}/media",
        files={"file": (name, data, mime)},
        data=fields,
        headers=headers,
    )


def stored(media_dir, url):
    return media_dir / url.removeprefix("/media/")


async def test_gps_is_stripped_and_rotation_applied(client, login, park_id, media_dir):
    response = await upload(client, park_id, await login("a@example.com"), jpeg_with_gps())
    assert response.status_code == 201
    with Image.open(stored(media_dir, response.json()["file_url"])) as image:
        assert not image.getexif()
        assert image.size == (400, 800)


async def test_heic_labelled_jpeg_is_accepted(client, login, park_id, media_dir):
    """Older app builds label every upload image/jpeg, including iPhone HEIC photos."""
    response = await upload(client, park_id, await login("a@example.com"), heic_bytes())
    assert response.status_code == 201
    assert response.json()["media_type"] == "image"
    assert response.json()["file_url"].endswith(".jpg")
    with Image.open(stored(media_dir, response.json()["thumbnail_url"])) as thumb:
        assert thumb.format == "JPEG" and thumb.width == 400


async def test_transparent_png_is_flattened(client, login, park_id):
    response = await upload(client, park_id, await login("a@example.com"), png_with_alpha(), mime="image/png")
    assert response.status_code == 201


@pytest.mark.parametrize(
    "data",
    [b"<html>not media</html>", b"\xff\xd8\xff" + b"garbage" * 50, b"\x00\x00\x00\x18ftypisom" + b"garbage" * 50],
    ids=["html", "fake-jpeg", "fake-video"],
)
async def test_bad_files_get_400_and_leave_nothing_behind(client, login, park_id, media_dir, data):
    response = await upload(client, park_id, await login("a@example.com"), data)
    if not shutil.which("ffmpeg") and b"ftypisom" in data:
        pytest.skip("ffmpeg not installed")
    assert response.status_code == 400
    assert not list((media_dir / park_id).glob("*")) if (media_dir / park_id).exists() else True


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
async def test_video_gets_thumbnail_and_loses_metadata(client, login, park_id, media_dir, tmp_path):
    source = tmp_path / "in.mov"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-metadata", "location=+29.7+095.3/", str(source)],
        check=True,
    )
    response = await upload(
        client, park_id, await login("a@example.com"), source.read_bytes(), "clip.mov", "image/jpeg"
    )
    assert response.status_code == 201
    body = response.json()
    assert body["media_type"] == "video" and body["file_url"].endswith(".mp4")
    assert stored(media_dir, body["thumbnail_url"]).stat().st_size > 0
    assert b"+29.7" not in stored(media_dir, body["file_url"]).read_bytes()


async def test_heic_avatar_works_and_replaces_old_file(client, login, media_dir):
    headers = await login("a@example.com")
    first = await client.post("/user/me/avatar", files={"file": ("a.jpg", heic_bytes(), "image/jpeg")}, headers=headers)
    assert first.status_code == 200
    first_path = stored(media_dir, first.json()["avatar_url"])
    assert first_path.exists()

    second = await client.post("/user/me/avatar", files={"file": ("a.jpg", jpeg_with_gps(), "image/jpeg")}, headers=headers)
    assert second.status_code == 200
    assert not first_path.exists()
    with Image.open(stored(media_dir, second.json()["avatar_url"])) as image:
        assert image.size == (512, 512)


async def test_avatar_rejects_garbage_with_400(client, login):
    response = await client.post(
        "/user/me/avatar", files={"file": ("a.jpg", b"nope", "image/jpeg")}, headers=await login("a@example.com")
    )
    assert response.status_code == 400


async def test_review_queue_approve_flow(client, login, park_id):
    user = await login("a@example.com")
    admin = await login("boss@example.com")
    media_id = (await upload(client, park_id, user, jpeg_with_gps(), description="sick")).json()["id"]

    assert (await client.get(f"/parks/{park_id}/media")).json() == []
    assert (await client.get("/media/review-queue", headers=user)).status_code == 403

    queue = (await client.get("/media/review-queue", headers=admin)).json()
    assert [item["id"] for item in queue] == [media_id]
    assert queue[0]["park_name"] == "Test Park"

    bad = await client.post(f"/media/{media_id}/approve", json={"action": "nope"}, headers=admin)
    assert bad.status_code == 422
    assert (await client.post(f"/media/{media_id}/approve", json={"action": "approve"}, headers=user)).status_code == 403
    assert (await client.post(f"/media/{media_id}/approve", json={"action": "approve"}, headers=admin)).status_code == 200

    assert (await client.get("/media/review-queue", headers=admin)).json() == []
    public = (await client.get(f"/parks/{park_id}/media")).json()
    assert [item["id"] for item in public] == [media_id]


async def approved_media(client, login, park_id, email="a@example.com"):
    user = await login(email)
    admin = await login("boss@example.com")
    media_id = (await upload(client, park_id, user, jpeg_with_gps())).json()["id"]
    await client.post(f"/media/{media_id}/approve", json={"action": "approve"}, headers=admin)
    return media_id, user, admin


async def test_reported_media_returns_to_queue_and_can_be_removed(client, login, park_id, sent_emails):
    media_id, _, admin = await approved_media(client, login, park_id)
    reporter = await login("c@example.com")

    before = len(sent_emails)
    for _ in range(2):
        response = await client.post(f"/media/{media_id}/report", json={"reason": "spam"}, headers=reporter)
        assert response.status_code == 204
    assert len(sent_emails) == before + 1

    queue = (await client.get("/media/review-queue", headers=admin)).json()
    assert queue[0]["id"] == media_id and queue[0]["report_count"] == 1

    await client.post(f"/media/{media_id}/approve", json={"action": "reject"}, headers=admin)
    assert (await client.get("/media/review-queue", headers=admin)).json() == []
    assert (await client.get(f"/parks/{park_id}/media")).json() == []


async def test_reporting_requires_login(client, login, park_id):
    media_id, _, _ = await approved_media(client, login, park_id)
    assert (await client.post(f"/media/{media_id}/report", json={})).status_code == 401


async def test_blocking_hides_media_only_for_the_blocker(client, login, park_id):
    media_id, user, _ = await approved_media(client, login, park_id)
    author_id = (await client.get("/user/me", headers=user)).json()["id"]
    viewer = await login("v@example.com")

    assert (await client.post(f"/user/{author_id}/block", headers=viewer)).status_code == 204
    assert (await client.post(f"/user/{author_id}/block", headers=viewer)).status_code == 204

    assert (await client.get(f"/parks/{park_id}/media", headers=viewer)).json() == []
    assert (await client.get(f"/parks/{park_id}", headers=viewer)).json()["media"] == []
    assert len((await client.get(f"/parks/{park_id}/media")).json()) == 1

    assert (await client.delete(f"/user/{author_id}/block", headers=viewer)).status_code == 204
    assert len((await client.get(f"/parks/{park_id}/media", headers=viewer)).json()) == 1


async def test_cannot_block_yourself(client, login):
    headers = await login("a@example.com")
    my_id = (await client.get("/user/me", headers=headers)).json()["id"]
    assert (await client.post(f"/user/{my_id}/block", headers=headers)).status_code == 400


async def test_expired_token_still_gets_public_data(client, park_id):
    response = await client.get(f"/parks/{park_id}", headers={"Authorization": "Bearer junk"})
    assert response.status_code == 200


async def test_account_deletion_removes_everything(client, login, park_id, media_dir, sent_emails):
    media_id, user, admin = await approved_media(client, login, park_id)
    item = (await client.get(f"/parks/{park_id}/media")).json()[0]
    file_path = stored(media_dir, item["file_url"])
    assert file_path.exists()
    await client.post("/favorites", json={"park_id": park_id}, headers=user)

    assert (await client.delete("/user/me", headers=user)).status_code == 204

    assert not file_path.exists()
    assert (await client.get(f"/parks/{park_id}/media")).json() == []
    assert (await client.get("/user/me", headers=user)).status_code == 401
    assert (await client.delete("/user/me", headers=admin)).status_code == 204


async def test_admin_who_reviewed_media_can_delete_account(client, login, park_id):
    _, _, admin = await approved_media(client, login, park_id)
    assert (await client.delete("/user/me", headers=admin)).status_code == 204
    assert len((await client.get(f"/parks/{park_id}/media")).json()) == 1
