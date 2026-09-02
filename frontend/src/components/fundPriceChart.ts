import type { FundOrder } from "../types/api";

export interface FundOperationPoint {
  x: string;
  y: number;
  order: FundOrder;
}

export interface FundOperationMarker extends FundOperationPoint {
  id: string;
  buy: boolean;
  operationCount: number;
  sourceOrders: FundOrder[];
}

const FUND_ENTRY_TYPES = new Set(["buy", "transfer_in"]);

export function isFundEntryOperation(order: FundOrder) {
  return FUND_ENTRY_TYPES.has(order.operation_type);
}

function nearestDate(target: string, dates: string[]) {
  const exact = dates.indexOf(target);
  if (exact >= 0) return dates[exact];
  const targetTime = Date.parse(target);
  return dates.reduce(
    (nearest, date) =>
      Math.abs(Date.parse(date) - targetTime) <
      Math.abs(Date.parse(nearest) - targetTime)
        ? date
        : nearest,
    dates[0],
  );
}

export function visibleFundOperationPoints(
  orders: FundOrder[],
  dates: string[],
): FundOperationPoint[] {
  if (!dates.length) return [];
  const start = dates[0];
  const end = dates.at(-1) ?? start;

  return orders
    .filter((order) => {
      const operationDate = order.trade_date.slice(0, 10);
      return operationDate >= start && operationDate <= end;
    })
    .map((order) => ({
      x: nearestDate(order.trade_date.slice(0, 10), dates),
      y: order.base_unit_price ?? order.unit_price,
      order,
    }));
}

function amountForOrder(order: FundOrder) {
  return order.base_net_amount ?? order.net_amount;
}

function priceForOrder(order: FundOrder) {
  return order.base_unit_price ?? order.unit_price;
}

/**
 * Keep chart markers legible when several fund movements share a trading day.
 * Entries and exits are kept separate because they have different visual accents.
 */
export function groupFundOperationPoints(
  points: FundOperationPoint[],
): FundOperationMarker[] {
  const groups = new Map<string, FundOperationPoint[]>();
  points.forEach((point) => {
    // The x label may be a weekly/monthly price point. Never use it as the
    // operation identity or distinct real trading days would be merged.
    const operationDate = point.order.trade_date.slice(0, 10);
    const key = `${operationDate}:${point.order.isin}:${isFundEntryOperation(point.order) ? "buy" : "sell"}`;
    groups.set(key, [...(groups.get(key) ?? []), point]);
  });

  return Array.from(groups.values()).map((group) => {
    const first = group[0];
    const sourceOrders = group.map(({ order }) => order);
    const titles = sourceOrders.reduce(
      (total, order) => total + order.quantity,
      0,
    );
    const weightedPrice = sourceOrders.reduce(
      (total, order) => total + priceForOrder(order) * order.quantity,
      0,
    );
    const sameAccount = sourceOrders.every(
      (order) =>
        order.account_name === first.order.account_name &&
        order.platform === first.order.platform,
    );
    const operation: FundOrder = {
      ...first.order,
      id: sourceOrders.map((order) => order.id).join(":"),
      quantity: titles,
      unit_price:
        titles > 0 ? weightedPrice / titles : priceForOrder(first.order),
      net_amount: sourceOrders.reduce(
        (total, order) => total + order.net_amount,
        0,
      ),
      ...(sourceOrders.some((order) => order.base_net_amount != null)
        ? {
            base_net_amount: sourceOrders.reduce(
              (total, order) => total + amountForOrder(order),
              0,
            ),
          }
        : {}),
      ...(sourceOrders.some((order) => order.base_unit_price != null)
        ? {
            base_unit_price:
              titles > 0 ? weightedPrice / titles : priceForOrder(first.order),
          }
        : {}),
      account_name: sameAccount ? first.order.account_name : "",
      platform: sameAccount ? first.order.platform : "",
    };
    const buy = isFundEntryOperation(first.order);
    return {
      id: `${first.x}:${buy ? "buy" : "sell"}:${sourceOrders.map((order) => order.id).join(":")}`,
      x: first.x,
      y: operation.base_unit_price ?? operation.unit_price,
      order: operation,
      buy,
      operationCount: sourceOrders.length,
      sourceOrders,
    };
  });
}
