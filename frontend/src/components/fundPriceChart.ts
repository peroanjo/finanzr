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

const FUND_ENTRY_TYPES = new Set([
  "SUSCRIPCION",
  "SUSCR.POR TRASPASO I",
  "COMPRA",
]);

export function isFundEntryOperation(order: FundOrder) {
  return FUND_ENTRY_TYPES.has(order.tipo_operacion.trim().toUpperCase());
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
      const operationDate = order.fecha_operacion.slice(0, 10);
      return operationDate >= start && operationDate <= end;
    })
    .map((order) => ({
      x: nearestDate(order.fecha_operacion.slice(0, 10), dates),
      y: order.precio_base ?? order.precio_neto,
      order,
    }));
}

function amountForOrder(order: FundOrder) {
  return order.importe_base ?? order.importe_neto;
}

function priceForOrder(order: FundOrder) {
  return order.precio_base ?? order.precio_neto;
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
    const operationDate = point.order.fecha_operacion.slice(0, 10);
    const key = `${operationDate}:${point.order.isin}:${isFundEntryOperation(point.order) ? "buy" : "sell"}`;
    groups.set(key, [...(groups.get(key) ?? []), point]);
  });

  return Array.from(groups.values()).map((group) => {
    const first = group[0];
    const sourceOrders = group.map(({ order }) => order);
    const titles = sourceOrders.reduce(
      (total, order) => total + order.titulos,
      0,
    );
    const weightedPrice = sourceOrders.reduce(
      (total, order) => total + priceForOrder(order) * order.titulos,
      0,
    );
    const sameAccount = sourceOrders.every(
      (order) =>
        order.cuenta_nombre === first.order.cuenta_nombre &&
        order.plataforma === first.order.plataforma,
    );
    const operation: FundOrder = {
      ...first.order,
      operacion_id: sourceOrders.map((order) => order.operacion_id).join(":"),
      titulos: titles,
      precio_neto:
        titles > 0 ? weightedPrice / titles : priceForOrder(first.order),
      importe_neto: sourceOrders.reduce(
        (total, order) => total + order.importe_neto,
        0,
      ),
      ...(sourceOrders.some((order) => order.importe_base != null)
        ? {
            importe_base: sourceOrders.reduce(
              (total, order) => total + amountForOrder(order),
              0,
            ),
          }
        : {}),
      ...(sourceOrders.some((order) => order.precio_base != null)
        ? {
            precio_base:
              titles > 0 ? weightedPrice / titles : priceForOrder(first.order),
          }
        : {}),
      cuenta_nombre: sameAccount ? first.order.cuenta_nombre : "",
      plataforma: sameAccount ? first.order.plataforma : "",
    };
    const buy = isFundEntryOperation(first.order);
    return {
      id: `${first.x}:${buy ? "buy" : "sell"}:${sourceOrders.map((order) => order.operacion_id).join(":")}`,
      x: first.x,
      y: operation.precio_base ?? operation.precio_neto,
      order: operation,
      buy,
      operationCount: sourceOrders.length,
      sourceOrders,
    };
  });
}
