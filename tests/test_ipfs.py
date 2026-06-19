from src.blockchain.ipfs import IPFSOffChainStore


class TestIPFSOffChainStore:
    def test_pin_returns_cid(self):
        store = IPFSOffChainStore()
        cid = store.pin({"hello": "world"})
        assert isinstance(cid, str)
        assert len(cid) == 46

    def test_get_returns_data(self):
        store = IPFSOffChainStore()
        data = {"test": 42}
        cid = store.pin(data, "test_type")
        retrieved = store.get(cid)
        assert retrieved is not None
        assert retrieved == data

    def test_get_returns_none_for_missing(self):
        store = IPFSOffChainStore()
        assert store.get("nonexistent") is None

    def test_pin_returns_same_cid_for_same_data(self):
        store = IPFSOffChainStore()
        data = {"dedup": True}
        cid1 = store.pin(data)
        cid2 = store.pin(data)
        assert cid1 == cid2

    def test_pin_lot_metadata(self):
        store = IPFSOffChainStore()
        cid = store.pin_lot_metadata(
            "lot_1", 100, {"lat": 1.0, "lng": 2.0}, "city"
        )
        assert isinstance(cid, str)
        data = store.get(cid)
        assert data is not None
        assert data["lot_id"] == "lot_1"

    def test_pin_price_history(self):
        store = IPFSOffChainStore()
        cid = store.pin_price_history(
            "zone_1", [{"time": "12:00", "price": 10.0}]
        )
        data = store.get(cid)
        assert data is not None
        assert data["zone_id"] == "zone_1"

    def test_summary(self):
        store = IPFSOffChainStore()
        store.pin({"a": 1}, "type_a")
        store.pin({"b": 2}, "type_b")
        s = store.summary()
        assert s["total_pins"] >= 2
        assert s["total_objects"] >= 2
        assert "type_a" in s["content_types"]
