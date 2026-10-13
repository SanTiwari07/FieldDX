def test_inbox_order_and_dismissals(client):
    body = client.get("/api/cases").json()
    rows = body["cases"]
    assert rows[0]["id"] == "C1"
    dismissed = [r for r in rows if r["outcome"] == "auto_dismissed"]
    assert len(dismissed) == 3 and all(r["reason"] for r in dismissed)
    assert rows[-1]["outcome"] == "auto_dismissed"
    assert "Simulated" in body["banner"]


def test_stream_has_steps_evidence_and_narrative(client):
    with client.stream("GET", "/api/cases/C1/investigate?pace=0") as resp:
        text = "".join(resp.iter_text())
    assert text.count("event: evidence") == 7
    assert "event: diagnosis" in text and "event: narrative" in text
    assert text.rstrip().endswith("data: {}")


def test_close_case_reranks_and_adds_evidence(client):
    r = client.post("/api/cases/C1/close", json={"check_id": "drip_line", "outcome": "dry", "note": "Valve blocked"})
    assert r.status_code == 200
    j = r.json()
    assert j["outcome"] == "resolved"
    assert j["evidence"][-1]["id"] == "E8" and j["evidence"][-1]["source"] == "Officer field visit"
    assert j["resolution"]["confirmed_id"] == "H7"
    assert client.get("/api/cases/C1").json()["outcome"] == "resolved"
    assert client.post("/api/cases/C1/close", json={"check_id": "drip_line", "outcome": "dry"}).status_code == 409


def test_wet_result_moves_the_ranking(client):
    j = client.post("/api/cases/C1/close", json={"check_id": "drip_line", "outcome": "wet"}).json()
    assert j["resolution"]["ranking_before"][0] == "H7"
    assert j["resolution"]["confirmed_id"] != "H7"


def test_bad_close_requests(client):
    assert client.post("/api/cases/C1/close", json={"check_id": "nope", "outcome": "dry"}).status_code == 422
    assert client.post("/api/cases/C1/close", json={"check_id": "drip_line", "outcome": "nope"}).status_code == 422
    assert client.post("/api/cases/C2/close", json={"check_id": "drip_line", "outcome": "dry"}).status_code == 422
    assert client.get("/api/cases/C99").status_code == 404


def test_map_and_series(client):
    m = client.get("/api/cases/C1/map").json()
    assert len(m["zones"]) == 8 and any(z["affected"] for z in m["zones"])
    s = client.get("/api/cases/C1/series").json()
    assert s["scenes"][0]["date"] == "2026-07-07" and s["expected"]
    cloudy = next(x for x in s["scenes"] if x["quality"] == "cloudy")
    assert all(v["ndvi"] is None for v in cloudy["zones"].values())


def test_raster_masks_clouds_and_shows_the_edge(client):
    r = client.get("/api/cases/C1/raster").json()
    assert r["w"] >= 15 and r["h"] >= 10 and r["quality"] == "usable"
    east = [row[-1] for row in r["ndvi"]]
    west = [row[0] for row in r["ndvi"]]
    assert sum(east) / len(east) < sum(west) / len(west) - 0.1  # the east edge drop is visible per pixel
    cloudy = client.get("/api/cases/C1/raster?scene=2026-07-17").json()
    assert cloudy["quality"] == "cloudy" and cloudy["stats"] is None
    assert all(v is None for row in cloudy["ndvi"] for v in row)  # never a number for a cloudy scene
    haze = client.get("/api/cases/C2/raster?scene=2026-10-05").json()
    assert 0 < sum(map(sum, haze["mask"])) < haze["w"] * haze["h"]
    assert client.get("/api/cases/C1/raster?scene=2026-07-18").status_code == 404
    assert client.get("/api/cases/C1/raster?scene=nope").status_code == 422
