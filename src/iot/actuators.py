"""Actuator bridge for parking infrastructure commands."""


class ActuatorBridge:
    def __init__(self):
        self.zones = {}

    def register_zone(self, zone_id: str):
        if zone_id not in self.zones:
            self.zones[zone_id] = {"signage": "normal", "barrier": "closed"}

    def actuate(self, zone_id: str, occupancy: float, price: float, multiplier: float):
        if zone_id not in self.zones:
            self.register_zone(zone_id)
        if occupancy > 0.85:
            self.zones[zone_id]["signage"] = "full"
            self.zones[zone_id]["barrier"] = "restricted"
        elif occupancy > 0.7:
            self.zones[zone_id]["signage"] = "busy"
            self.zones[zone_id]["barrier"] = "normal"
        else:
            self.zones[zone_id]["signage"] = "available"
            self.zones[zone_id]["barrier"] = "open"

    def summary(self) -> dict:
        return {k: v for k, v in self.zones.items()}
