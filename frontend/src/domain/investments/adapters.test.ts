import { describe, expect, it } from "vitest";
import {
  adaptCryptoChart,
  adaptFundChart,
  adaptStockChart,
  toInvestmentOverviewPosition,
} from "./adapters";
import type {
  CryptoChartResponse,
  CryptoInstrument,
  FundChartResponse,
  FundInstrument,
  NativePosition,
  StockChartResponse,
  StockInstrument,
} from "../../types/api";

describe("normalized investment adapters", () => {
  it("preserves nullable overview values and direct fund return", () => {
    const position = toInvestmentOverviewPosition(
      {
        instrument_id: "00000000-0000-0000-0000-000000000012",
        kind: "fund",
        name: "Global fund",
        asset_class: "Renta Variable",
        subtype: "Global",
        quantity: null as unknown as number,
        cost: null as unknown as number,
        average_price: 0,
        current_price: null,
        current_value: null,
        unrealized_pnl: null,
        realized_pnl: null,
        currency: "gbp",
        base_currency: "usd",
        return_percent: null,
      } as NativePosition,
      {
        id: "00000000-0000-0000-0000-000000000012",
        kind: "fund",
        name: "Instrument name",
        quote_currency: "EUR",
        identifiers: [
          { scheme: "isin", value: "LU000", venue: "", is_primary: true },
          { scheme: "yahoo", value: "GLOBAL", venue: "", is_primary: true },
        ],
        asset_class: "RV",
        subtype: "Index",
        is_active: true,
      } as FundInstrument,
      null,
    );

    expect(position).toMatchObject({
      assetKey: "fund:00000000-0000-0000-0000-000000000012",
      displayIdentifier: "LU000",
      name: "Global fund",
      quantity: 0,
      cost: 0,
      currentPrice: null,
      currentValue: null,
      unrealizedPnl: null,
      returnPercent: null,
    });
  });

  it("maps stock and crypto positions to distinct stable keys", () => {
    const stock = toInvestmentOverviewPosition(
      {
        instrument_id: "00000000-0000-0000-0000-000000000401",
        kind: "stock",
        name: "Company",
        quantity: 2,
        cost: 100,
        current_price: 60,
        current_value: 120,
        unrealized_pnl: 20,
        realized_pnl: -3,
        currency: "USD",
        base_currency: "EUR",
      } as NativePosition,
      {
        id: "00000000-0000-0000-0000-000000000401",
        kind: "stock",
        name: "Company",
        quote_currency: "USD",
        identifiers: [
          { scheme: "isin", value: "US000", venue: "", is_primary: true },
          { scheme: "yahoo", value: "CMP", venue: "", is_primary: true },
        ],
        asset_class: null,
        subtype: null,
        is_active: true,
      } as StockInstrument,
    );
    const crypto = toInvestmentOverviewPosition(
      {
        instrument_id: "00000000-0000-0000-0000-000000000402",
        kind: "crypto",
        name: "Bitcoin",
        quantity: 0.1,
        cost: 2000,
        current_price: null,
        current_value: null,
        unrealized_pnl: null,
        realized_pnl: 40,
        currency: "EUR",
        base_currency: "EUR",
      } as NativePosition,
      {
        id: "00000000-0000-0000-0000-000000000402",
        kind: "crypto",
        name: "Bitcoin",
        quote_currency: "EUR",
        identifiers: [
          {
            scheme: "crypto_symbol",
            value: "BTC",
            venue: "",
            is_primary: true,
          },
          { scheme: "yahoo", value: "BTC-EUR", venue: "", is_primary: true },
        ],
        asset_class: null,
        subtype: null,
        is_active: true,
      } as CryptoInstrument,
    );

    expect(stock).toMatchObject({
      assetKey: "stock:00000000-0000-0000-0000-000000000401",
      displayIdentifier: "US000",
      quantity: 2,
      cost: 100,
      currentPrice: 60,
      currentValue: 120,
      unrealizedPnl: 20,
      returnPercent: null,
    });
    expect(crypto).toMatchObject({
      assetKey: "crypto:00000000-0000-0000-0000-000000000402",
      displayIdentifier: "BTC",
      currentPrice: null,
      currentValue: null,
      unrealizedPnl: null,
      returnPercent: null,
    });
  });

  it("maps OHLC market candles, fund prices and empty chart data", () => {
    const fundChart = adaptFundChart({
      instrument_id: "00000000-0000-0000-0000-000000000101",
      ticker: "GLOBAL",
      currency: "GBP",
      base_currency: "USD",
      range: "1y",
      data: [{ date: "2026-01-01", close: 42 }],
    } as FundChartResponse);
    const explicitChartBase = adaptStockChart({
      instrument_id: "00000000-0000-0000-0000-000000000102",
      ticker: "CMP",
      currency: "GBP",
      base_currency: "USD",
      range: "1y",
      data: [
        {
          date: "2026-01-01",
          open: 48,
          high: 52,
          low: 47,
          close: 50,
        },
      ],
    } as StockChartResponse);
    const emptyChart = adaptStockChart({
      instrument_id: "00000000-0000-0000-0000-000000000102",
      ticker: "CMP",
      currency: "USD",
      base_currency: "USD",
      range: "1y",
      data: null as never,
    } as StockChartResponse);

    expect(fundChart).toEqual([
      {
        date: "2026-01-01",
        price: 42,
      },
    ]);
    expect(explicitChartBase).toEqual([
      {
        date: "2026-01-01",
        open: 48,
        high: 52,
        low: 47,
        close: 50,
      },
    ]);
    expect(emptyChart).toEqual([]);
  });

  it("maps OHLC market candles and crypto chart identity without changing DTOs", () => {
    const chart = adaptCryptoChart({
      instrument_id: "00000000-0000-0000-0000-000000000201",
      ticker: "BTC-EUR",
      currency: "EUR",
      base_currency: "EUR",
      range: "1y",
      data: [
        {
          date: "2026-01-01",
          open: 50000,
          high: 52000,
          low: 49000,
          close: 51000,
        },
      ],
    } as CryptoChartResponse);

    expect(chart).toEqual([
      {
        date: "2026-01-01",
        open: 50000,
        high: 52000,
        low: 49000,
        close: 51000,
      },
    ]);
  });

  it("filters market candles with missing or non-finite OHLC fields", () => {
    const chart = adaptStockChart({
      instrument_id: "00000000-0000-0000-0000-000000000102",
      ticker: "CMP",
      currency: "USD",
      base_currency: "USD",
      range: "1y",
      data: [
        {
          date: "2026-01-01",
          open: 48,
          high: 52,
          low: 47,
          close: 50,
        },
        {
          date: "2026-01-02",
          open: null as unknown as number,
          high: 53,
          low: 49,
          close: 51,
        },
        {
          date: "2026-01-03",
          open: 50,
          high: Number.NaN,
          low: 49,
          close: 52,
        },
        {
          date: "2026-01-04",
          open: 51,
          high: 55,
          low: 50,
        } as never,
      ],
    } as StockChartResponse);

    expect(chart).toEqual([
      {
        date: "2026-01-01",
        open: 48,
        high: 52,
        low: 47,
        close: 50,
      },
    ]);
  });
});
