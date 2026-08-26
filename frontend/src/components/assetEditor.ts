import type { CryptoInstrument, StockInstrument } from "../types/api";

export type EditableAsset = CryptoInstrument | StockInstrument;

export interface AssetEditorHandle {
  openCreate: () => void;
  openEdit: (asset?: EditableAsset | null) => void;
}
