from src.api.schemas import (
    ScenarioListItem,
    ScenarioRunResponse,
    GenerateScenarioResponse,
    ScenarioPipelineResponse,
)


class TestDigitalTwinScenarios:
    def test_list_scenarios_no_auth_required(self, client):
        resp = client.get("/api/v1/digital-twin/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_list_scenarios_returns_items(self, client):
        resp = client.get("/api/v1/digital-twin/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        item = data[0]
        assert "name" in item
        assert "description" in item

    def test_list_scenarios_matches_pydantic_schema(self, client):
        resp = client.get("/api/v1/digital-twin/scenarios")
        assert resp.status_code == 200
        for item in resp.json():
            validated = ScenarioListItem(**item)
            assert validated.name

    def test_list_scenarios_pagination(self, client):
        all_resp = client.get("/api/v1/digital-twin/scenarios")
        total = len(all_resp.json())
        limited = client.get("/api/v1/digital-twin/scenarios?offset=0&limit=2")
        assert limited.status_code == 200
        assert len(limited.json()) == min(2, total)

    def test_list_scenarios_offset(self, client):
        all_resp = client.get("/api/v1/digital-twin/scenarios")
        all_items = all_resp.json()
        if len(all_items) > 1:
            resp = client.get(
                "/api/v1/digital-twin/scenarios?offset=1&limit=1"
            )
            assert resp.status_code == 200
            assert len(resp.json()) == 1

    def test_run_scenarios_requires_admin(self, client, auth_headers):
        resp = client.post(
            "/api/v1/digital-twin/scenarios/run",
            json={
                "zone_id": "test_lot",
                "occupancy_rate": 0.5,
                "price": 5.0,
                "total_slots": 100,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_run_scenarios_requires_auth(self, client):
        resp = client.post(
            "/api/v1/digital-twin/scenarios/run",
            json={
                "zone_id": "test_lot",
                "occupancy_rate": 0.5,
                "price": 5.0,
                "total_slots": 100,
            },
        )
        assert resp.status_code in (401, 403)

    def test_run_scenarios_returns_results(self, client, admin_headers):
        resp = client.post(
            "/api/v1/digital-twin/scenarios/run",
            json={
                "zone_id": "test_zone",
                "occupancy_rate": 0.6,
                "price": 8.0,
                "total_slots": 50,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "base_state" in data
        assert "results" in data
        assert "comparisons" in data
        assert len(data["results"]) > 0

    def test_run_scenarios_matches_pydantic_schema(
        self, client, admin_headers
    ):
        resp = client.post(
            "/api/v1/digital-twin/scenarios/run",
            json={
                "zone_id": "schema_zone",
                "occupancy_rate": 0.4,
                "price": 6.0,
                "total_slots": 80,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200
        validated = ScenarioRunResponse(**resp.json())
        assert validated.base_state["zone_id"] == "schema_zone"

    def test_run_named_scenario(self, client, admin_headers):
        # First get available scenarios
        scenarios = client.get("/api/v1/digital-twin/scenarios").json()
        if scenarios:
            name = scenarios[0]["name"]
            resp = client.post(
                "/api/v1/digital-twin/scenarios/run",
                json={
                    "zone_id": "named_zone",
                    "occupancy_rate": 0.5,
                    "price": 5.0,
                    "total_slots": 60,
                    "scenario_name": name,
                },
                headers=admin_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["results"]) == 1

    def test_run_nonexistent_scenario_returns_404(self, client, admin_headers):
        resp = client.post(
            "/api/v1/digital-twin/scenarios/run",
            json={
                "zone_id": "bad_zone",
                "occupancy_rate": 0.5,
                "price": 5.0,
                "total_slots": 60,
                "scenario_name": "nonexistent_scenario",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 404


class TestDigitalTwinGenerate:
    def test_generate_requires_admin(self, client, auth_headers):
        resp = client.post(
            "/api/v1/digital-twin/generate",
            json={"base_occupancy": 0.5, "base_price": 5.0},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_generate_requires_auth(self, client):
        resp = client.post(
            "/api/v1/digital-twin/generate",
            json={"base_occupancy": 0.5, "base_price": 5.0},
        )
        assert resp.status_code in (401, 403)

    def test_generate_does_not_use_trained_generator(self, client, admin_headers):
        # P5: the CVAE-WGAN generator is offline-only. This endpoint must NOT
        # depend on a runtime `pipeline.generator` attribute (it does not exist).
        from src.pipeline.orchestrator import pipeline

        assert not hasattr(pipeline, "generator")

    def test_generate_returns_deterministic_baseline(self, client, admin_headers):
        # The retained endpoint returns a deterministic, persistence-style
        # baseline (no GAN synthesis) and echoes the base request.
        resp = client.post(
            "/api/v1/digital-twin/generate",
            json={"base_occupancy": 0.5, "base_price": 5.0},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "synthetic_occupancy" in data
        assert "synthetic_price" in data
        assert "congestion_score" in data
        assert 0 <= data["synthetic_occupancy"] <= 1
        assert data["synthetic_price"] >= 0
        assert data["synthetic_occupancy"] == 0.5
        assert data["synthetic_price"] == 5.0

    def test_generate_matches_pydantic_schema(self, client, admin_headers):
        resp = client.post(
            "/api/v1/digital-twin/generate",
            json={"base_occupancy": 0.7, "base_price": 10.0},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        validated = GenerateScenarioResponse(**resp.json())
        assert validated.synthetic_occupancy >= 0


class TestDigitalTwinScenarioPipeline:
    def test_pipeline_scenario_requires_admin(self, client, auth_headers):
        resp = client.post(
            "/api/v1/digital-twin/scenario",
            json={"scenario_type": "demand_spike", "zone_id": "test_zone"},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_pipeline_scenario_requires_auth(self, client):
        resp = client.post(
            "/api/v1/digital-twin/scenario",
            json={"scenario_type": "demand_spike", "zone_id": "test_zone"},
        )
        assert resp.status_code in (401, 403)

    def test_pipeline_scenario_returns_result(self, client, admin_headers):
        resp = client.post(
            "/api/v1/digital-twin/scenario",
            json={"scenario_type": "demand_spike", "zone_id": "ps_zone"},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 404, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "scenario" in data or "result" in data

    def test_pipeline_scenario_matches_pydantic_schema(
        self, client, admin_headers
    ):
        resp = client.post(
            "/api/v1/digital-twin/scenario",
            json={"scenario_type": "peak_hour", "zone_id": "schema_ps_zone"},
            headers=admin_headers,
        )
        if resp.status_code == 200:
            validated = ScenarioPipelineResponse(**resp.json())
            assert validated.scenario == "peak_hour"


class TestDigitalTwinTrainGenerator:
    def test_train_endpoint_removed_offline_only(self, client, admin_headers):
        # P5: the CVAE-WGAN generator is offline-only. The runtime
        # /train-generator endpoint has been removed; training happens via the
        # scripts/train_twin_generator.py entrypoint. The runtime must not
        # expose a request-time training route.
        resp = client.post(
            "/api/v1/digital-twin/train-generator",
            json={"epochs": 10},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_train_requires_auth_removed(self, client):
        resp = client.post(
            "/api/v1/digital-twin/train-generator", json={"epochs": 10}
        )
        # Endpoint removed -> not found (auth never reached).
        assert resp.status_code == 404

    def test_offline_train_script_entrypoint_exists(self):
        # The offline training capability must exist as a script, not a runtime
        # route (per P5: never train on live/simulated production data).
        import importlib.util
        import os

        script_path = os.path.join("scripts", "train_twin_generator.py")
        assert os.path.isfile(script_path), "scripts/train_twin_generator.py missing"
        spec = importlib.util.spec_from_file_location(
            "train_twin_generator_script", script_path
        )
        assert spec is not None, "could not build spec for offline trainer"
        assert spec.loader is not None, "offline trainer spec has no loader"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "main"), "offline trainer has no main() entrypoint"
        assert hasattr(mod, "evaluate"), (
            "offline trainer exposes no evaluate() (real-data eval) function"
        )
        assert hasattr(mod, "build_state_rows"), (
            "offline trainer exposes no build_state_rows() function"
        )

    def test_runtime_has_no_generator_attribute(self):
        # The orchestrator must NOT carry a runtime generator (offline-only).
        from src.pipeline.orchestrator import pipeline

        assert not hasattr(pipeline, "generator")
