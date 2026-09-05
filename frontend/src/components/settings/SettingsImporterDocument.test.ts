import { describe, expect, it } from "vitest";
import SettingsImporterDocument from "./SettingsImporterDocument.vue";
import { mountWithTestI18n } from "./testI18n";

describe("SettingsImporterDocument", () => {
  it("renders the importer contract and field metadata", () => {
    const wrapper = mountWithTestI18n(SettingsImporterDocument, {
      props: {
        selectedImporter: {
          slug: "synthetic_importer",
          display_name: "Synthetic importer",
          target: "stock_orders",
          target_label: "Stocks",
          description: "Synthetic description",
          source_instructions: "Download the synthetic export.",
          input_kind: "records",
          accepted_extensions: [".csv"],
          required_fields: ["trade_id"],
          formats: [
            {
              extension: ".csv",
              label: "CSV",
              description: "UTF-8 CSV",
            },
          ],
          fields: [
            {
              name: "trade_id",
              label: "Trade ID",
              description: "Unique synthetic identifier.",
              example: "SYN-001",
              required: true,
              position: 1,
            },
          ],
          rules: ["Only synthetic rows are accepted."],
        },
      },
    });

    expect(wrapper.get(".document-header h3").text()).toBe(
      "Synthetic importer",
    );
    expect(wrapper.get(".document-header > code").text()).toBe(
      "synthetic_importer",
    );
    expect(wrapper.get(".field-row strong").text()).toBe("Trade ID");
    expect(wrapper.get(".field-row > code").text()).toBe("SYN-001");
    expect(wrapper.text()).toContain("Only synthetic rows are accepted.");
  });

  it("does not render a document until an importer is selected", () => {
    const wrapper = mountWithTestI18n(SettingsImporterDocument, {
      props: { selectedImporter: null },
    });

    expect(wrapper.find(".importer-document").exists()).toBe(false);
  });
});
