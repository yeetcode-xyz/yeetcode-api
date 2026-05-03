def test_send_otp_no_auth(client):
    r = client.post("/send-otp", json={"email": "test@example.com", "code": "123456"})
    assert r.status_code == 403


def test_send_otp_bad_key(client):
    r = client.post(
        "/send-otp",
        json={"email": "test@example.com", "code": "123456"},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert r.status_code == 401


def test_send_otp_success(client, auth_headers):
    r = client.post(
        "/send-otp",
        json={"email": "test@example.com", "code": "123456"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_store_and_verify_code(client, auth_headers):
    email = "verify@example.com"
    code = "999888"

    r = client.post(
        "/store-verification-code",
        json={"email": email, "code": code},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["success"] is True

    r = client.post(
        "/verify-code",
        json={"email": email, "code": code},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True


def test_verify_wrong_code(client, auth_headers):
    email = "wrongcode@example.com"

    r = client.post(
        "/store-verification-code",
        json={"email": email, "code": "111111"},
        headers=auth_headers,
    )
    assert r.status_code == 200

    r = client.post(
        "/verify-code",
        json={"email": email, "code": "000000"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["success"] is False
