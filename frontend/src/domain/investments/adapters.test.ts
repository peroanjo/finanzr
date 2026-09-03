import { describe, expect, it } from "vitest";
import * as investmentBarrel from "./index";
import {
  adaptCryptoAccount,
  adaptCryptoChart,
  adaptCryptoPerformance,
  adaptCryptoMovement,
  adaptCryptoPosition,
  adaptFundAccount,
  adaptFundChart,
  adaptFundMovement,
  adaptFundPerformance,
  adaptFundPosition,
  adaptStockAccount,
  adaptStockChart,
  adaptStockMovement,
  adaptStockPosition,
  adaptStockPerformance,
} from "./adapters";
import type {
  CryptoChartResponse,
  CryptoOrder,
  CryptoPosition,
  CryptoPerformanceResponse,
  FundChartResponse,
  FundOrder,
  FundPerformanceResponse,
  FundPosition,
  StockChartResponse,
  StockInstrument,
  StockOrder,
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
        isin: "LU000",
        nombre: "Global fund",
        tipo: "Renta Variable",
        subtipo: "Global",
        total_invertido: null as unknown as number,
        participaciones: null as unknown as number,
        precio_medio: 0,
        precio_actual: null,
        valor_actual: null,
        pnl: null,
        pnl_pct: null,
        moneda: "gbp",
        moneda_base: "usd",
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
      assetId: "LU000",
      assetKey: "fund:LU000",
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
        isin: "US000",
        nombre: "Company",
        titulos: 2,
        coste_total: 100,
        precio_actual: 60,
        valor_actual: 120,
        pnl: 20,
        pnl_realizada: -3,
        moneda: "USD",
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
        symbol: "BTC",
        nombre: "Bitcoin",
        titulos: 0.1,
        coste_total: 2000,
        precio_actual: null,
        valor_actual: null,
        pnl: null,
        pnl_realizada: 40,
        moneda: "EUR",
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
      assetId: "US000",
      assetKey: "stock:US000",
      quantity: 2,
      cost: 100,
      currentPrice: 60,
      currentValue: 120,
      unrealizedPnl: 20,
      realizedPnl: -3,
      currency: "USD",
    });
    expect(crypto).toMatchObject({
      kind: "crypto",
      assetId: "BTC",
      assetKey: "crypto:BTC",
      type: "crypto",
      currentPrice: null,
      currentValue: null,
      unrealizedPnl: null,
      realizedPnl: 40,
      currency: "EUR",
    });
  });

  it("maps fund movements to base amounts while retaining original currency metadata", () => {
    const fundOrder: FundOrder = {
      id: "fund-1",
      trade_date: "2026-01-02",
      settlement_date: "2026-01-03",
      operation_type: "buy",
      cash_flow_type: "contribution",
      isin: "LU000",
      asset_name: "Global fund",
      quantity: 2,
      unit_price: 50,
      net_amount: 100,
      fee: 0,
      account_id: "00000000-0000-0000-0000-000000000001",
      currency: "USD",
      base_currency: "EUR",
      base_unit_price: 46,
      base_net_amount: 92,
      base_fee: 0,
      fx_rate_to_base: 0.92,
      fx_rate_date: "2026-01-02",
      fx_source: "test",
      market: "",
      account_name: "Broker",
      platform: "Broker",
      provider_operation_type: "SUSCRIPCION",
    };
    const movement = adaptFundMovement(fundOrder);

    expect(movement).toMatchObject({
      kind: "fund",
      id: "fund-1",
      assetId: "LU000",
      assetKey: "fund:LU000",
      date: "2026-01-02",
      quantity: 2,
      price: 46,
      cost: 92,
      amount: 92,
      fee: null,
      currency: "EUR",
      baseCurrency: "EUR",
      capabilities: { fees: false },
    });
    expect(movement.metadata).toMatchObject({
      originalCurrency: "USD",
      operationType: "buy",
      accountId: "00000000-0000-0000-0000-000000000001",
      accountName: "Broker",
      settlementDate: "2026-01-03",
    });

    const nonEurBase = adaptFundMovement({
      ...fundOrder,
      currency: "GBP",
      base_currency: "USD",
      net_amount: 100,
      unit_price: 50,
      base_net_amount: 80,
      base_unit_price: 40,
    });
    expect(nonEurBase).toMatchObject({ currency: "USD", baseCurrency: "USD" });
    expect(nonEurBase.metadata).toMatchObject({ originalCurrency: "GBP" });

    const dtoBaseWins = adaptFundMovement(
      {
        id: "fund-conflict",
        trade_date: "2026-01-02",
        settlement_date: "2026-01-03",
        operation_type: "buy",
        cash_flow_type: "contribution",
        isin: "LU000",
        asset_name: "Global fund",
        quantity: 2,
        unit_price: 50,
        net_amount: 100,
        fee: 0,
        account_id: "00000000-0000-0000-0000-000000000001",
        currency: "GBP",
        base_currency: "USD",
        base_unit_price: 40,
        base_net_amount: 80,
        base_fee: 0,
        fx_rate_to_base: 0.8,
        fx_rate_date: "2026-01-02",
        fx_source: "test",
        market: "",
        account_name: "Broker",
        platform: "Broker",
        provider_operation_type: "SUSCRIPCION",
      },
      { baseCurrency: "EUR" },
    );
    expect(dtoBaseWins).toMatchObject({ currency: "USD", baseCurrency: "USD" });
    expect(dtoBaseWins.metadata).toMatchObject({
      originalCurrency: "GBP",
      currencySource: "dto-base",
    });

    const explicitBaseWithoutDtoBase = adaptFundMovement(
      {
        ...fundOrder,
        currency: "GBP",
        base_currency: "",
        base_unit_price: null,
        base_net_amount: null,
        base_fee: null,
      },
      { baseCurrency: "USD" },
    );
    expect(explicitBaseWithoutDtoBase).toMatchObject({
      currency: "USD",
      baseCurrency: "USD",
    });
    expect(explicitBaseWithoutDtoBase.metadata).toMatchObject({
      originalCurrency: "GBP",
    });
  });

  it("keeps stock fees, saveback, and split capability metadata", () => {
    const movement = adaptStockMovement({
      id: "stock-1",
      trade_date: "2026-01-02",
      quantity: 3,
      net_amount: 300,
      fee: 2,
      account_id: "00000000-0000-0000-0000-000000000001",
      account_name: "Broker",
      platform: "Broker",
      operation_type: "buy",
      cash_flow_type: "none",
      isin: "US000",
      asset_name: "Company",
      unit_price: 100,
      is_saveback: true,
      currency: "USD",
      base_currency: "EUR",
      base_unit_price: 92,
      base_net_amount: 276,
      base_fee: 1.5,
      fx_rate_to_base: 0.92,
      fx_rate_date: "2026-01-02",
      fx_source: "test",
      market: "",
    } as StockOrder);

    expect(movement).toMatchObject({
      kind: "stock",
      price: 92,
      cost: 276,
      amount: 276,
      fee: 1.5,
      currency: "EUR",
      capabilities: { fees: true, saveback: true, splits: true },
    });
    expect(movement.metadata).toMatchObject({
      originalCurrency: "USD",
      saveback: true,
      splitAdjusted: false,
    });
  });

  it("maps crypto fees and leaves saveback and split support disabled", () => {
    const movement = adaptCryptoMovement({
      id: "crypto-1",
      trade_date: "2026-01-02",
      quantity: 0.01,
      net_amount: 500,
      fee: 1.2,
      account_id: "00000000-0000-0000-0000-000000000001",
      account_name: "Broker",
      platform: "Broker",
      operation_type: "buy",
      cash_flow_type: "none",
      symbol: "BTC",
      asset_name: "Bitcoin",
      unit_price: 50000,
      currency: "EUR",
      base_currency: "EUR",
      base_unit_price: 50000,
      base_net_amount: 500,
      base_fee: 1.2,
      fx_rate_to_base: 1,
      fx_rate_date: "2026-01-02",
      fx_source: "identity",
      market: "",
    } as CryptoOrder);

    expect(movement).toMatchObject({
      kind: "crypto",
      assetId: "BTC",
      price: 50000,
      cost: 500,
      amount: 500,
      fee: 1.2,
      currency: "EUR",
      capabilities: { fees: true, saveback: false, splits: false },
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
