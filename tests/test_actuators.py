from src.iot.actuators import (
    SmartBarrier,
    DigitalPricingBoard,
    CongestionLight,
    ActuatorBridge,
)


class TestSmartBarrier:
    def test_initial_state(self):
        b = SmartBarrier("bar_1", "zone_1")
        assert b.is_open is True
        assert b.restricted is False
        assert b.reservation_only is False

    def test_set_restricted(self):
        b = SmartBarrier("bar_1", "zone_1")
        cmd = b.set_restricted(True)
        assert b.restricted is True
        assert b.is_open is False
        assert cmd.command_type == "barrier:restrict"
        assert cmd.value == 1.0

    def test_set_restricted_reverse(self):
        b = SmartBarrier("bar_1", "zone_1")
        b.set_restricted(True)
        b.set_restricted(False)
        assert b.restricted is False
        assert b.is_open is True

    def test_set_reservation_only(self):
        b = SmartBarrier("bar_1", "zone_1")
        cmd = b.set_reservation_only(True)
        assert b.reservation_only is True
        assert b.is_open is False
        assert cmd.command_type == "barrier:reservation_only"

    def test_status(self):
        b = SmartBarrier("bar_1", "zone_1")
        s = b.status()
        assert s["barrier_id"] == "bar_1"
        assert s["open"] is True


class TestDigitalPricingBoard:
    def test_initial_price(self):
        b = DigitalPricingBoard("board_1", "zone_1")
        assert b.displayed_price == 10.0

    def test_set_price(self):
        b = DigitalPricingBoard("board_1", "zone_1")
        cmd = b.set_price(15.50)
        assert b.displayed_price == 15.50
        assert cmd.command_type == "pricing:update"
        assert cmd.value == 15.50

    def test_status(self):
        b = DigitalPricingBoard("board_1", "zone_1")
        s = b.status()
        assert s["board_id"] == "board_1"
        assert s["displayed_price"] == 10.0


class TestCongestionLight:
    def test_initial_color(self):
        light = CongestionLight("light_1", "zone_1")
        assert light.color == "green"

    def test_set_green(self):
        light = CongestionLight("light_1", "zone_1")
        cmd = light.set_color("green")
        assert light.color == "green"
        assert light.flashing is False
        assert cmd.value == 0

    def test_set_red(self):
        light = CongestionLight("light_1", "zone_1")
        cmd = light.set_color("red")
        assert light.color == "red"
        assert light.flashing is True
        assert cmd.value == 2

    def test_set_yellow(self):
        light = CongestionLight("light_1", "zone_1")
        cmd = light.set_color("yellow")
        assert light.color == "yellow"
        assert cmd.value == 1

    def test_status(self):
        light = CongestionLight("light_1", "zone_1")
        s = light.status()
        assert s["light_id"] == "light_1"
        assert s["color"] == "green"


class TestActuatorBridge:
    def test_register_zone(self):
        b = ActuatorBridge()
        b.register_zone("zone_1")
        assert "zone_1" in b.barriers
        assert "zone_1" in b.boards
        assert "zone_1" in b.lights

    def test_actuate_normal(self):
        b = ActuatorBridge()
        b.register_zone("zone_1")
        result = b.actuate("zone_1", 0.3, 10.0, 0.0)
        assert result["zone_id"] == "zone_1"
        assert b.lights["zone_1"].color == "green"

    def test_actuate_congested(self):
        b = ActuatorBridge()
        b.register_zone("zone_1")
        b.actuate("zone_1", 0.90, 20.0, 0.0)
        assert b.lights["zone_1"].color == "red"
        assert b.barriers["zone_1"].restricted is True

    def test_actuate_moderate(self):
        b = ActuatorBridge()
        b.register_zone("zone_1")
        b.actuate("zone_1", 0.75, 15.0, 0.0)
        assert b.lights["zone_1"].color == "yellow"

    def test_actuate_price_set(self):
        b = ActuatorBridge()
        b.register_zone("zone_1")
        result = b.actuate("zone_1", 0.3, 12.50, 0.0)
        assert result["price_set"] == 12.50
        assert b.boards["zone_1"].displayed_price == 12.50

    def test_summary(self):
        b = ActuatorBridge()
        b.register_zone("zone_1")
        b.actuate("zone_1", 0.3, 10.0, 0.0)
        s = b.summary()
        assert s["zones_registered"] == 1
        assert s["total_commands"] >= 1
