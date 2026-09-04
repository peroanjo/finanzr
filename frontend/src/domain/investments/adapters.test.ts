import { describe, expect, it } from "vitest";
import * as investmentBarrel from "./index";
import {
  adaptCryptoAccount,
  adaptCryptoChart,
  adaptCryptoPerformance,
  adaptCryptoPosition,
  adaptFundAccount,
  adaptFundChart,
  adaptFundPerformance,
  adaptFundPosition,
  adaptStockAccount,
  adaptStockChart,
  adaptStockPosition,
  adaptStockPerformance,
} from "./adapters";
import type {
  CryptoChartResponse,
  CryptoPosition,
  CryptoPerformanceResponse,
  FundChartResponse,
  FundPerformanceResponse,
  FundPosition,
  StockChartResponse,
  StockInstrument,
  StockPerformanceResponse,
  StockPosition,
  CryptoInstrument,
} from "../../types/api";

describe("normalized investment adapters", () => {
  it("exports stock and crypto performance through the investments barrel", () => {
    expect(investmentBarrel.adaptStockPerformance).toBe(adaptStockPerformance);
    expect(investmentBarrel.adaptCryptoPerformance).toBe(
      adaptCryptoPerformance,
    );
  });

  it("normalizes accounts with a stable id, currency, and source metadata", () => {
    const fund = adaptFundAccount({
      id: "00000000-0000-0000-0000-000000000007",
      name: "Index funds",
      platform: "Broker",
      type: "renta_variable",
      currency: "usd",
      importer_slug: "fund_csv",
      importer_name: "Fund CSV",
    });
    const stock = adaptStockAccount({
      id: "00000000-0000-0000-0000-000000000008",
      name: "Stocks",
      platform: "Trade Republic",
      type: "",
      currency: "EUR",
      importer_slug: "tr",
      importer_name: "Trade Republic",
    });
    const crypto = adaptCryptoAccount({
      id: "00000000-0000-0000-0000-000000000009",
      name: "Kraken",
      platform: "KrakenPro",
      type: "",
      currency: "eur",
      importer_slug: "kraken",
      importer_name: "Kraken",
    });

    expect(fund).toMatchObject({
      kind: "fund",
      id: "00000000-0000-0000-0000-000000000007",
      currency: "USD",
      type: "renta_variable",
      capabilities: { fees: false, saveback: false, splits: false },
    });
    expect(fund.metadata).toMatchObject({
      source: "fund-account",
      importerSlug: "fund_csv",
    });
    expect(stock).toMatchObject({
      kind: "stock",
      id: "00000000-0000-0000-0000-000000000008",
      type: null,
      currency: "EUR",
    });
    expect(stock.capabilities).toMatchObject({
      fees: true,
      saveback: true,
      splits: true,
    });
    expect(crypto).toMatchObject({
      kind: "crypto",
      id: "00000000-0000-0000-0000-000000000009",
      currency: "EUR",
    });
    expect(crypto.capabilities).toMatchObject({
      fees: true,
      saveback: false,
      splits: false,
    });
  });

  it("preserves nullable fund position values and instrument metadata", () => {
    const position = adaptFundPosition(
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
      } as FundPosition,
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
      },
    );

    expect(position).toMatchObject({
      kind: "fund",
      assetId: "00000000-0000-0000-0000-000000000012",
      assetKey: "fund:00000000-0000-0000-0000-000000000012",
      displayIdentifier: "LU000",
      name: "Global fund",
      type: "Renta Variable",
      subtype: "Global",
      quantity: 0,
      cost: 0,
      currentPrice: null,
      currentValue: null,
      unrealizedPnl: null,
      realizedPnl: null,
      currency: "USD",
      baseCurrency: "USD",
    });
    expect(position.metadata).toMatchObject({
      ticker: "GLOBAL",
      returnPercent: null,
      originalCurrency: "GBP",
    });
  });

  it("maps stock and crypto positions to distinct discriminated keys", () => {
    const stock = adaptStockPosition(
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
      } as StockPosition,
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
    const crypto = adaptCryptoPosition(
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
      } as CryptoPosition,
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
      kind: "stock",
      assetId: "00000000-0000-0000-0000-000000000401",
      assetKey: "stock:00000000-0000-0000-0000-000000000401",
      displayIdentifier: "US000",
      quantity: 2,
      cost: 100,
      currentPrice: 60,
      currentValue: 120,
      unrealizedPnl: 20,
      realizedPnl: -3,
      currency: "EUR",
    });
    expect(crypto).toMatchObject({
      kind: "crypto",
      assetId: "00000000-0000-0000-0000-000000000402",
      assetKey: "crypto:00000000-0000-0000-0000-000000000402",
      displayIdentifier: "BTC",
      type: "crypto",
      currentPrice: null,
      currentValue: null,
      unrealizedPnl: null,
      realizedPnl: 40,
      currency: "EUR",
    });
  });

  it("normalizes fund performance and chart responses, including empty/null data", () => {
    const performance = adaptFundPerformance(
      {
        range: "1y",
        account_id: "00000000-0000-0000-0000-000000000002",
        moneda_base: "EUR",
        data: [
          {
            fecha: "2026-01-01",
            valor: 100,
            invertido: 100,
            pnl: 0,
            pnl_pct: 0,
          },
        ],
      } as FundPerformanceResponse,
      { baseCurrency: "EUR" },
    );
    const fundChart = adaptFundChart({
      instrument_id: "00000000-0000-0000-0000-000000000101",
      ticker: "GLOBAL",
      currency: "GBP",
      base_currency: "USD",
      range: "1y",
      data: [{ date: "2026-01-01", close: 42 }],
    } as FundChartResponse);
    const explicitChartBase = adaptStockChart(
      {
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
      } as StockChartResponse,
      { baseCurrency: "USD" },
    );
    const emptyChart = adaptStockChart({
      instrument_id: "00000000-0000-0000-0000-000000000102",
      ticker: "CMP",
      currency: "USD",
      base_currency: "USD",
      range: "1y",
      data: null as never,
    } as StockChartResponse);

    expect(performance).toMatchObject({
      kind: "fund",
      accountId: "00000000-0000-0000-0000-000000000002",
      range: "1y",
      currency: "EUR",
      baseCurrency: "EUR",
    });
    expect(performance.data[0]).toEqual({
      date: "2026-01-01",
      value: 100,
      invested: 100,
      pnl: 0,
      pnlPercent: 0,
    });
    expect(fundChart).toMatchObject({
      kind: "fund",
      assetId: "00000000-0000-0000-0000-000000000101",
      assetKey: "fund:00000000-0000-0000-0000-000000000101",
      currency: "USD",
      baseCurrency: "USD",
      seriesKind: "line",
    });
    expect(explicitChartBase).toMatchObject({
      currency: "USD",
      baseCurrency: "USD",
      seriesKind: "candlestick",
      metadata: { originalCurrency: "GBP" },
    });
    expect(explicitChartBase.data[0]).toEqual({
      seriesKind: "candlestick",
      date: "2026-01-01",
      open: 48,
      high: 52,
      low: 47,
      close: 50,
    });
    expect(fundChart.data[0]).toMatchObject({
      seriesKind: "line",
      date: "2026-01-01",
      price: 42,
    });
    expect(
      adaptFundPerformance({
        range: "1y",
        account_id: "all",
        moneda_base: "",
        data: [],
      } as FundPerformanceResponse),
    ).toMatchObject({ currency: "UNSPECIFIED", baseCurrency: null });
    expect(emptyChart).toMatchObject({
      kind: "stock",
      assetId: "00000000-0000-0000-0000-000000000102",
      currency: "USD",
      data: [],
    });
  });

  it("normalizes stock performance with stock capabilities and reporting currency", () => {
    const performance = adaptStockPerformance({
      range: "1y",
      account_id: "all",
      moneda_base: "EUR",
      data: [
        {
          fecha: "2026-01-01",
          valor: 100,
          invertido: 90,
          pnl: 10,
          pnl_pct: 11.11,
        },
      ],
    } as StockPerformanceResponse);

    expect(performance).toMatchObject({
      kind: "stock",
      accountId: "all",
      currency: "EUR",
      baseCurrency: "EUR",
      capabilities: { fees: true, saveback: true, splits: true },
    });
    expect(performance.data).toEqual([
      {
        date: "2026-01-01",
        value: 100,
        invested: 90,
        pnl: 10,
        pnlPercent: 11.11,
      },
    ]);
  });

  it("normalizes crypto performance with the crypto capability contract", () => {
    const performance = adaptCryptoPerformance({
      range: "2y",
      account_id: "all",
      moneda_base: "EUR",
      data: [
        {
          fecha: "2026-01-01",
          valor: 1250,
          invertido: 1000,
          pnl: 250,
          pnl_pct: 25,
        },
      ],
    } as CryptoPerformanceResponse);

    expect(performance).toMatchObject({
      kind: "crypto",
      accountId: "all",
      range: "2y",
      currency: "EUR",
      baseCurrency: "EUR",
      metadata: { source: "crypto-performance", currencySource: "dto-base" },
      capabilities: { fees: true, saveback: false, splits: false },
    });
    expect(performance.data).toEqual([
      {
        date: "2026-01-01",
        value: 1250,
        invested: 1000,
        pnl: 250,
        pnlPercent: 25,
      },
    ]);
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

    expect(chart).toMatchObject({
      kind: "crypto",
      assetId: "00000000-0000-0000-0000-000000000201",
      assetKey: "crypto:00000000-0000-0000-0000-000000000201",
      ticker: "BTC-EUR",
      currency: "EUR",
      baseCurrency: "EUR",
    });
    expect(chart.data[0]).toEqual({
      seriesKind: "candlestick",
      date: "2026-01-01",
      open: 50000,
      high: 52000,
      low: 49000,
      close: 51000,
    });
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

    expect(chart.data).toEqual([
      {
        seriesKind: "candlestick",
        date: "2026-01-01",
        open: 48,
        high: 52,
        low: 47,
        close: 50,
      },
    ]);
  });
});
