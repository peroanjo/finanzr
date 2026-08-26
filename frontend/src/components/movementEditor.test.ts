import { describe, expect, it } from "vitest";
import { movementAssetIdentifier } from "./movementEditor";

describe("movementAssetIdentifier", () => {
  it("uses ISIN for funds and stocks, and symbol only for crypto", () => {
    expect(movementAssetIdentifier("fund", "ES0000000001")).toEqual({
      isin: "ES0000000001",
    });
    expect(movementAssetIdentifier("stock", "US67066G1040")).toEqual({
      isin: "US67066G1040",
    });
    expect(movementAssetIdentifier("crypto", "BTC")).toEqual({
      symbol: "BTC",
    });
  });
});
