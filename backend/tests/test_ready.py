async def test_ready_returns_ready_after_lifespan(client):
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
