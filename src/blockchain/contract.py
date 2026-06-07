from typing import Callable, Dict


class SmartContract:
    def __init__(self, contract_id: str, owner: str, logic: Callable):
        self.contract_id = contract_id
        self.owner = owner
        self.logic = logic
        self.state: Dict = {}

    def execute(self, context: dict) -> dict:
        return self.logic(self.state, context)

    def get_state(self) -> dict:
        return self.state


class RevenueShareContract(SmartContract):
    """Revenue sharing with a configurable system fee (default 15%).

    On each payment:
      1. system_fee_ratio is deducted as platform fee (recorded as "system").
      2. Remaining amount is distributed among share_ratios participants.

    Whitepaper: "Distributes a fixed 15% system fee to stakeholders,
    then splits remaining revenue among city and lot operators."
    """

    def __init__(self, contract_id: str, owner: str,
                 share_ratios: Dict[str, float],
                 system_fee_ratio: float = 0.15):
        self.system_fee_ratio = system_fee_ratio

        def revenue_logic(state: dict, ctx: dict) -> dict:
            price = ctx.get("price", 0)
            system_fee = round(price * system_fee_ratio, 2)
            after_fee = round(price - system_fee, 2)

            total_shares = sum(share_ratios.values())
            distributions = {"system": system_fee}
            state["system"] = state.get("system", 0) + system_fee

            for participant, ratio in share_ratios.items():
                share = (after_fee * ratio) / total_shares if total_shares > 0 else 0.0
                distributions[participant] = round(share, 2)
                state[participant] = state.get(participant, 0) + share

            return {"distributions": distributions, "remaining": 0.0}

        super().__init__(contract_id, owner, revenue_logic)
        self.share_ratios = share_ratios


class AllocationContract(SmartContract):
    def __init__(self, contract_id: str, owner: str):
        def allocation_logic(state: dict, ctx: dict) -> dict:
            driver_id = ctx.get("driver_id")
            lot_id = ctx.get("lot_id")
            price = ctx.get("price", 0)
            available_spots = ctx.get("available_spots", [])

            if not available_spots:
                return {"allocated": False, "reason": "no_spots"}

            spot_id = available_spots[0]
            allocation_key = f"{lot_id}:{spot_id}"
            state[allocation_key] = {
                "driver_id": driver_id,
                "price": price,
                "status": "allocated",
            }
            return {
                "allocated": True,
                "spot_id": spot_id,
                "lot_id": lot_id,
                "price": price,
                "allocation_key": allocation_key,
            }

        super().__init__(contract_id, owner, allocation_logic)
