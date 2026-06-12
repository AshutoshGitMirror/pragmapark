from collections import deque
from dataclasses import dataclass
from typing import Dict
from src.constants import CONGESTION_HIGH, CONGESTION_MODERATE


@dataclass
class ActuatorCommand:
    actuator_id: str
    command_type: str
    value: float
    target_zone: str
    timestamp: float


class SmartBarrier:
    def __init__(self, barrier_id: str, zone_id: str):
        self.barrier_id = barrier_id
        self.zone_id = zone_id
        self.is_open = True
        self.restricted = False
        self.reservation_only = False

    def set_restricted(self, restricted: bool) -> ActuatorCommand:
        self.restricted = restricted
        self.is_open = not restricted
        return ActuatorCommand(
            actuator_id=self.barrier_id,
            command_type="barrier:restrict",
            value=float(restricted),
            target_zone=self.zone_id,
            timestamp=0.0,
        )

    def set_reservation_only(self, active: bool) -> ActuatorCommand:
        self.reservation_only = active
        self.is_open = not active
        return ActuatorCommand(
            actuator_id=self.barrier_id,
            command_type="barrier:reservation_only",
            value=float(active),
            target_zone=self.zone_id,
            timestamp=0.0,
        )

    def status(self) -> dict:
        return {
            "barrier_id": self.barrier_id,
            "zone_id": self.zone_id,
            "open": self.is_open,
            "restricted": self.restricted,
            "reservation_only": self.reservation_only,
        }


class DigitalPricingBoard:
    def __init__(self, board_id: str, zone_id: str):
        self.board_id = board_id
        self.zone_id = zone_id
        self.displayed_price: float = 10.0
        self.last_updated: float = 0.0

    def set_price(self, price: float) -> ActuatorCommand:
        self.displayed_price = round(price, 2)
        self.last_updated = 0.0
        return ActuatorCommand(
            actuator_id=self.board_id,
            command_type="pricing:update",
            value=self.displayed_price,
            target_zone=self.zone_id,
            timestamp=0.0,
        )

    def status(self) -> dict:
        return {
            "board_id": self.board_id,
            "zone_id": self.zone_id,
            "displayed_price": self.displayed_price,
        }


class CongestionLight:
    def __init__(self, light_id: str, zone_id: str):
        self.light_id = light_id
        self.zone_id = zone_id
        self.color: str = "green"
        self.flashing: bool = False

    def set_color(self, color: str) -> ActuatorCommand:
        self.color = color
        self.flashing = color == "red"
        return ActuatorCommand(
            actuator_id=self.light_id,
            command_type=f"light:{color}",
            value={"green": 0, "yellow": 1, "red": 2}.get(color, 0),
            target_zone=self.zone_id,
            timestamp=0.0,
        )

    def status(self) -> dict:
        return {
            "light_id": self.light_id,
            "color": self.color,
            "flashing": self.flashing,
        }


class ActuatorBridge:
    def __init__(self):
        self.barriers: Dict[str, SmartBarrier] = {}
        self.boards: Dict[str, DigitalPricingBoard] = {}
        self.lights: Dict[str, CongestionLight] = {}
        self.command_log: deque = deque(maxlen=500)

    def register_zone(self, zone_id: str) -> None:
        self.barriers[zone_id] = SmartBarrier(f"barrier_{zone_id}", zone_id)
        self.boards[zone_id] = DigitalPricingBoard(f"board_{zone_id}", zone_id)
        self.lights[zone_id] = CongestionLight(f"light_{zone_id}", zone_id)

    def actuate(
        self,
        zone_id: str,
        occupancy_rate: float,
        rl_price: float,
        rl_action: float,
    ) -> dict:
        # Auto-register unknown zones on first actuation
        if zone_id not in self.boards:
            self.register_zone(zone_id)
        commands = []
        price_cmd = self.boards[zone_id].set_price(rl_price)
        commands.append(price_cmd)
        if occupancy_rate > CONGESTION_HIGH:
            barrier_cmd = self.barriers[zone_id].set_restricted(True)
            light_cmd = self.lights[zone_id].set_color("red")
            commands.extend([barrier_cmd, light_cmd])
        elif occupancy_rate > CONGESTION_MODERATE:
            self.barriers[zone_id].set_restricted(False)
            light_cmd = self.lights[zone_id].set_color("yellow")
            commands.append(light_cmd)
        else:
            self.barriers[zone_id].set_restricted(False)
            light_cmd = self.lights[zone_id].set_color("green")
            commands.append(light_cmd)
        if rl_action < -0.05:
            barrier_cmd = self.barriers[zone_id].set_reservation_only(False)
            commands.append(barrier_cmd)
        self.command_log.extend(commands)
        return {
            "zone_id": zone_id,
            "commands": [c.command_type for c in commands],
            "price_set": rl_price,
        }

    def zone_statuses(self) -> list[dict]:
        """Return per-zone actuator status for all registered zones."""
        zones = []
        for zone_id in self.barriers:
            zones.append(
                {
                    "zone_id": zone_id,
                    "barrier": self.barriers[zone_id].status(),
                    "pricing_board": self.boards[zone_id].status(),
                    "congestion_light": self.lights[zone_id].status(),
                }
            )
        return zones

    def summary(self) -> dict:
        return {
            "zones_registered": len(self.barriers),
            "total_commands": len(self.command_log),
            "last_commands": [
                c.command_type for c in list(self.command_log)[-5:]
            ],
        }
