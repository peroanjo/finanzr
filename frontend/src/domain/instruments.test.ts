import { describe, expect, it } from "vitest";
import {
  instrumentByIdentity,
  instrumentCurrency,
  instrumentIdentity,
  instrumentName,
  instrumentTicker,
} from "./instruments";
import type { StockInstrument } from "../types/api";

const stock: StockInstrument = {
  id: "00000000-0000-0000-0000-000000000013",
  kind: "stock",
  name: "Synthetic Apple",
  quote_currency: "USD",
  identifiers: [
    { scheme: "isin", value: "US0000000001", venue: "", is_primary: false },
    { scheme: "yahoo", value: "AAPL.MC", venue: "BME", is_primary: true },
    { scheme: "yahoo", value: "AAPL", venue: "", is_primary: false },
  ],
  asset_class: "Equity",
  subtype: null,
  is_active: true,
};

describe("native instrument helpers", () => {
  it("resolve canonical identity and primary provider ticker from identifiers", () => {
    expect(instrumentIdentity(stock)).toBe("US0000000001");
    expect(instrumentTicker(stock)).toBe("AAPL.MC");
    expect(instrumentName(stock)).toBe("Synthetic Apple");
    expect(instrumentCurrency(stock)).toBe("USD");
    expect(instrumentByIdentity([stock], "US0000000001")).toBe(stock);
  });

  it("prefers a default venue when no provider identifier is primary", () => {
    const withoutPrimary = {
      ...stock,
      identifiers: stock.identifiers.map((item) => ({
        ...item,
        is_primary: false,
      })),
    };
    expect(instrumentTicker(withoutPrimary)).toBe("AAPL");
  });

  it("uses backend-compatible ordinal ordering for nondefault provider venues", () => {
    const ordinalFixture = {
      ...stock,
      identifiers: [
        {
          scheme: "isin" as const,
          value: "US0000000001",
          venue: "",
          is_primary: false,
        },
        {
          scheme: "yahoo" as const,
          value: "Z.MC",
          venue: "BME",
          is_primary: false,
        },
        {
          scheme: "yahoo" as const,
          value: "a.MC",
          venue: "BME",
          is_primary: false,
        },
      ],
    };
    expect(instrumentTicker(ordinalFixture)).toBe("Z.MC");
  });
});
