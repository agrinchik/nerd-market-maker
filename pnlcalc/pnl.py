import numpy as np


class PnLCalculator:
    def __init__(self):
        self.qty = 0
        self.cost = 0.0
        self.mkt_val = 0.0
        self.unrealised_pnl = 0.0
        self.realized_pnl = 0.0
        self.avg_price = 0.0

    def fill(self, fill_qty, price):
        direction = np.sign(fill_qty)
        prev_direction = np.sign(self.qty)

        if prev_direction == direction:
            qty_closing = 0
            qty_opening = fill_qty
        else:
            qty_closing = min(abs(self.qty), abs(fill_qty)) * direction
            qty_opening = fill_qty - qty_closing

        new_cost = self.cost + qty_opening * price
        if self.qty != 0:
            new_cost += qty_closing * self.cost / self.qty
            self.realized_pnl += qty_closing * (self.cost / self.qty - price)

        self.qty += fill_qty
        self.cost = new_cost

        if self.qty != 0:
            self.avg_price = self.cost / self.qty
        else:
            self.avg_price = 0.0

        self.mkt_val = self.qty * price
        self.unrealised_pnl = self.mkt_val - self.cost

