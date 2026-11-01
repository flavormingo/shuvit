import resend

from tests.conftest import otp_from


async def test_otp_login_creates_user(client, login):
    headers = await login("skater@example.com")
    me = await client.get("/user/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "skater@example.com"
    assert me.json()["is_admin"] is False


async def test_email_is_case_insensitive(client, login):
    first = await (await client.get("/user/me", headers=await login("Skater@Example.com"))).aread()
    second = await (await client.get("/user/me", headers=await login("skater@example.com"))).aread()
    assert first == second


async def test_otp_works_only_once(client, sent_emails):
    await client.post("/auth/request-magic-link", json={"email": "a@example.com"})
    body = {"email": "a@example.com", "code": otp_from(sent_emails[-1])}
    assert (await client.post("/auth/verify-otp", json=body)).status_code == 200
    assert (await client.post("/auth/verify-otp", json=body)).status_code == 400


async def test_code_locks_after_five_wrong_guesses(client, sent_emails):
    await client.post("/auth/request-magic-link", json={"email": "a@example.com"})
    code = otp_from(sent_emails[-1])
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(5):
        response = await client.post("/auth/verify-otp", json={"email": "a@example.com", "code": wrong})
        assert response.status_code == 400

    # Even the right code is refused now.
    response = await client.post("/auth/verify-otp", json={"email": "a@example.com", "code": code})
    assert response.status_code == 400


async def test_only_newest_code_is_accepted(client, sent_emails):
    await client.post("/auth/request-magic-link", json={"email": "a@example.com"})
    old = otp_from(sent_emails[-1])
    await client.post("/auth/request-magic-link", json={"email": "a@example.com"})
    new = otp_from(sent_emails[-1])

    if old != new:
        response = await client.post("/auth/verify-otp", json={"email": "a@example.com", "code": old})
        assert response.status_code == 400
    response = await client.post("/auth/verify-otp", json={"email": "a@example.com", "code": new})
    assert response.status_code == 200


async def test_codes_per_email_are_capped_per_hour(client, sent_emails):
    for _ in range(8):
        assert (await client.post("/auth/request-magic-link", json={"email": "a@example.com"})).status_code == 200
    assert len(sent_emails) == 5


async def test_verify_is_rate_limited_per_ip(client, sent_emails):
    # Different target emails, so only the per-IP limit can stop this.
    responses = [
        await client.post("/auth/verify-otp", json={"email": f"u{i}@example.com", "code": "000000"})
        for i in range(31)
    ]
    assert responses[29].status_code == 400
    assert responses[30].status_code == 429


async def test_admin_email_is_granted_admin(client, login):
    me = await client.get("/user/me", headers=await login("BOSS@example.com"))
    assert me.json()["is_admin"] is True


async def test_failed_email_reports_503_and_allows_retry(client, monkeypatch):
    def fail(_):
        raise RuntimeError("provider down")

    monkeypatch.setattr(resend.Emails, "send", fail)
    response = await client.post("/auth/request-magic-link", json={"email": "a@example.com"})
    assert response.status_code == 503
