import { describe, expect, it } from "vitest";
import type { StockOrder } from "../types/api";
import { applyAdHocChartOperationFixes } from "./chartOperationFixes";

const bydOrder = (date: string): StockOrder => ({
  operacion_id: `byd-${date}`,
  fecha_operacion: date,
  titulos: 1,
  importe_neto: 34.07,
  cuenta_id: 1,
  cuenta_nombre: "Trade Republic",
  plataforma: "Trade Republic",
  tipo_operacion: "Compra",
  isin: "CNE100000296",
  nombre_activo: "BYD",
  precio_compra: 34.07,
  comision: 0,
  es_saveback: false,
});

describe("applyAdHocChartOperationFixes", () => {
  it("adjusts only BYD operations before June 10, 2025", () => {
    const february = bydOrder("2025-02-03");
    const juneNinth = bydOrder("2025-06-09");
    const splitDate = bydOrder("2025-06-10");

    const [adjustedFebruary, adjustedJuneNinth, untouchedSplitDate] =
      applyAdHocChartOperationFixes([february, juneNinth, splitDate]);

    expect(adjustedFebruary.titulos).toBe(3);
    expect(adjustedFebruary.precio_compra).toBeCloseTo(34.07 / 3);
    expect(adjustedFebruary.chartAdjustment).toEqual({
      id: "byd-pre-june-10-2025-split-3-to-1",
      label: "Split BYD 3:1",
    });
    expect(adjustedJuneNinth.titulos).toBe(3);
    expect(adjustedJuneNinth.precio_compra).toBeCloseTo(34.07 / 3);
    expect(untouchedSplitDate).toEqual(splitDate);
    expect(february.titulos).toBe(1);
    expect(february.precio_compra).toBe(34.07);
  });

  it("does not modify other assets", () => {
    const other = { ...bydOrder("2025-02-03"), isin: "US67066G1040" };

    expect(applyAdHocChartOperationFixes([other])).toEqual([other]);
  });
});
