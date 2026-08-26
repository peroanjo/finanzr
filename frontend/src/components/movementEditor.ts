import type { CryptoOrder, FundOrder, StockOrder } from "../types/api";

export interface MovementAssetOption {
  id: string;
  label: string;
  currency?: string;
}

export interface MovementEditorHandle {
  openCreate: () => void;
  openEdit: (movement: FundOrder | CryptoOrder | StockOrder) => void;
}

export interface MovementDeleteHandle {
  open: (movement: FundOrder | CryptoOrder | StockOrder) => void;
}

export type MovementKind = "fund" | "stock" | "crypto";

export function movementAssetIdentifier(
  kind: MovementKind,
  assetId: string,
): { isin: string } | { symbol: string } {
  return kind === "crypto" ? { symbol: assetId } : { isin: assetId };
}
