def test_samples_api_lists_manifest_entries(client) -> None:
    response = client.get("/api/samples")

    assert response.status_code == 200
    payload = response.json()
    sample_ids = [sample["id"] for sample in payload["samples"]]
    assert "happy-fullstack" in sample_ids
    assert "edge-ambiguous" in sample_ids


def test_samples_api_serves_sample_resume(client) -> None:
    response = client.get("/api/samples/happy-fullstack/resume")

    assert response.status_code == 200
    assert "Rajesh Gurung" in response.text
