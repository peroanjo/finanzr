import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { NormalizedPosition } from "../../domain/investments";
import InvestmentOverview from "./InvestmentOverview.vue";

const labels = {
  assets: {
    section: "Assets",
    title: "Top assets",
    asset: "Asset",
    portfolioValue: "Value",
    contributed: "Cost",
    currentPrice: "Price",
    averagePrice: "Average",
    value: "Value",
    return: "Return",
    pnl: "P&L",
    pending: "Pending",
    emptyTitle: "No assets",
    emptyDescription: "No positions",
  },
  kpis: {
    section: "Summary",
    title: "Portfolio",
    portfolioValue: "Value",
    openAsset: "{count} asset",
    openAssets: "{count} assets",
    unrealizedPnl: "Unrealized",
    versusCost: "{return} return",
    realizedPnl: "Realized",
    recordedSales: "Recorded sales",
    totalPnl: "Total",
    realizedAndOpen: "Realized and open",
    marketData: "Market data",
    updating: "Updating",
    update: "Update",
  },
};

function position(
  kind: NormalizedPosition["kind"],
  assetId: string,
  displayIdentifier: string,
): NormalizedPosition {
  return {
    kind,
    assetId,
    assetKey: `${kind}:${assetId}`,
    displayIdentifier,
    name: `${kind} asset`,
    type: null,
    subtype: null,
    quantity: 1,
    cost: 10,
    currentPrice: 11,
    currentValue: 11,
    unrealizedPnl: 1,
    realizedPnl: 0,
    currency: "EUR",
    baseCurrency: "EUR",
    metadata: {},
    capabilities: { fees: true, saveback: false, splits: false },
  };
}

describe("InvestmentOverview", () => {
  it("renders canonical identifiers without exposing technical UUIDs", () => {
    const uuids = [
      "00000000-0000-0000-0000-000000000101",
      "00000000-0000-0000-0000-000000000102",
      "00000000-0000-0000-0000-000000000103",
    ];
    const wrapper = mount(InvestmentOverview, {
      props: {
        topPositions: [
          position("fund", uuids[0], "LU0000000001"),
          position("stock", uuids[1], "US0000000002"),
          position("crypto", uuids[2], "BTC"),
        ],
        openPositionsCount: 3,
        totalValue: 33,
        unrealizedPnl: 3,
        openReturn: 0.1,
        realizedPnl: 0,
        totalPnl: 3,
        latestUpdate: "Now",
        priceMessage: "",
        refreshingPrices: false,
        currencyLabel: "EUR",
        assetReturnMode: "pnl",
        labels,
        formatMoney: (value: number) => String(value),
        formatPercentage: (value: number) => String(value),
        formatSignedMoney: (value: number) => String(value),
      },
      global: { stubs: { AssetReturnToggle: true } },
    });

    const identifiers = wrapper
      .findAll(".fund-asset-id small")
      .map((item) => item.text());
    expect(identifiers).toEqual(["LU0000000001", "US0000000002", "BTC"]);
    expect(uuids.some((uuid) => wrapper.text().includes(uuid))).toBe(false);
  });
});
