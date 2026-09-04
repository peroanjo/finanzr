import type {
  CryptoInstrument,
  FundInstrument,
  InstrumentIdentifier,
  StockInstrument,
} from "../types/api";

export type NativeInstrument =
  FundInstrument | StockInstrument | CryptoInstrument;

export function primaryIdentifier(
  instrument: NativeInstrument | undefined,
  scheme: InstrumentIdentifier["scheme"],
): InstrumentIdentifier | undefined {
  const canonical = scheme === "isin" || scheme === "crypto_symbol";
  return (instrument?.identifiers ?? [])
    .filter(
      (item) => item.scheme === scheme && (!canonical || item.venue === ""),
    )
    .sort((left, right) => {
      if (!canonical) {
        const primary = Number(right.is_primary) - Number(left.is_primary);
        if (primary) return primary;
        const venue = Number(left.venue !== "") - Number(right.venue !== "");
        if (venue) return venue;
      }
      if (left.value < right.value) return -1;
      if (left.value > right.value) return 1;
      if (left.venue < right.venue) return -1;
      if (left.venue > right.venue) return 1;
      return 0;
    })[0];
}

export function identifier(
  instrument: NativeInstrument | undefined,
  scheme: InstrumentIdentifier["scheme"],
): string {
  const match = primaryIdentifier(instrument, scheme);
  return match?.value ?? "";
}

export function instrumentIdentity(
  instrument: NativeInstrument | undefined,
): string {
  if (!instrument) return "";
  return identifier(
    instrument,
    instrument.kind === "crypto" ? "crypto_symbol" : "isin",
  );
}

export function instrumentTicker(
  instrument: NativeInstrument | undefined,
): string {
  return identifier(instrument, "yahoo");
}

export function instrumentName(
  instrument: NativeInstrument | undefined,
  fallback = "",
): string {
  return instrument?.name ?? fallback;
}

export function instrumentCurrency(
  instrument: NativeInstrument | undefined,
  fallback = "EUR",
): string {
  return instrument?.quote_currency ?? fallback;
}

export function instrumentByIdentity<T extends NativeInstrument>(
  instruments: T[],
  identity: string,
): T | undefined {
  return instruments.find((item) => instrumentIdentity(item) === identity);
}

export function instrumentById<T extends NativeInstrument>(
  instruments: T[],
  id: string,
): T | undefined {
  return instruments.find((item) => item.id === id);
}
