import { describe, expect, it } from "vitest";
import { coreMessages } from "./coreMessages";
import { cryptoMessages } from "./cryptoMessages";
import { fundsMessages } from "./fundsMessages";
import { stocksMessages } from "./stocksMessages";
import { viewMessagesA } from "./viewMessagesA";
import { realEstateMessages } from "./realEstateMessages";
import { sharedMessages } from "./sharedMessages";
import { apiMessages } from "./apiMessages";

function keys(value: unknown, prefix = ""): string[] {
  if (!value || typeof value !== "object") return [prefix];
  return Object.entries(value).flatMap(([key, child]) =>
    keys(child, prefix ? `${prefix}.${key}` : key),
  );
}

describe("translation catalogs", () => {
  for (const [name, catalog] of Object.entries({
    coreMessages,
    viewMessagesA,
    realEstateMessages,
    fundsMessages,
    stocksMessages,
    cryptoMessages,
    sharedMessages,
    apiMessages,
  })) {
    it(`${name} uses English as its source and has a complete Spanish translation`, () => {
      const englishSourceKeys = keys(catalog.en).sort();
      expect(Object.keys(catalog)[0]).toBe("en");
      expect(keys(catalog["es-ES"]).sort()).toEqual(englishSourceKeys);
    });
  }
});
