def test_get_nonexistent_user(client, auth_headers):
    r = client.get("/user/nobody", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["success"] is False


def test_create_and_get_user(client, auth_headers):
    r = client.post(
        "/create-user-with-username",
        json={"username": "testuser", "email": "testuser@example.com", "display_name": "Test User"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["success"] is True

    r = client.get("/user/testuser", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["data"]["username"] == "testuser"
    assert data["data"]["email"] == "testuser@example.com"


def test_leaderboard(client, auth_headers):
    r = client.get("/leaderboard", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "users" in data or "leaderboard" in data or isinstance(data, list) or data.get("success") is not None
