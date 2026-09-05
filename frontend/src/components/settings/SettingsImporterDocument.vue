<script setup lang="ts">
import { useI18n } from "vue-i18n";
import type { ImporterCatalogItem } from "../../types/api";

defineProps<{
  selectedImporter: ImporterCatalogItem | null;
}>();

const { t } = useI18n();
</script>

<template>
  <article v-if="selectedImporter" class="importer-document">
    <header class="document-header">
      <div>
        <p>
          {{
            t("settings.importContract", {
              target: selectedImporter.target_label,
            })
          }}
        </p>
        <h3>{{ selectedImporter.display_name }}</h3>
        <span><i /> {{ t("common.configured") }}</span>
      </div>
      <code>{{ selectedImporter.slug }}</code>
    </header>

    <p class="document-description">
      {{ selectedImporter.description }}
    </p>
    <div class="source-note">
      <span aria-hidden="true">↓</span>
      <p>
        <strong>{{ t("settings.howToGetIt") }}</strong
        >{{ selectedImporter.source_instructions }}
      </p>
    </div>

    <section class="document-section">
      <header>
        <div>
          <p>01</p>
          <h4>{{ t("settings.supportedFormats") }}</h4>
        </div>
        <span>{{ selectedImporter.formats.length }}</span>
      </header>
      <div class="format-grid">
        <div
          v-for="format in selectedImporter.formats"
          :key="format.extension"
        >
          <span>{{ format.extension.replace(".", "").toUpperCase() }}</span>
          <p>
            <strong>{{ format.label }}</strong
            ><small>{{ format.description }}</small>
          </p>
        </div>
      </div>
    </section>

    <section class="document-section fields-section">
      <header>
        <div>
          <p>02</p>
          <h4>{{ t("settings.expectedStructure") }}</h4>
        </div>
        <span>
          {{
            t("settings.fieldsSummary", {
              fields: selectedImporter.fields.length,
              required: selectedImporter.required_fields.length,
            })
          }}
        </span>
      </header>
      <div class="field-table">
        <div class="field-head">
          <span>{{ t("settings.field") }}</span
          ><span>{{ t("settings.expectedContent") }}</span
          ><span>{{ t("settings.example") }}</span>
        </div>
        <div
          v-for="field in selectedImporter.fields"
          :key="field.name"
          class="field-row"
        >
          <div>
            <b v-if="field.position">{{ String(field.position).padStart(2, "0") }}</b>
            <span>
              <strong>{{ field.label }}</strong
              ><code>{{ field.name }}</code>
            </span>
          </div>
          <p>
            {{ field.description }}
            <em>{{ field.required ? t("common.required") : t("common.optional") }}</em>
          </p>
          <code>{{ field.example }}</code>
        </div>
      </div>
    </section>

    <section class="document-section rules-section">
      <header>
        <div>
          <p>03</p>
          <h4>{{ t("settings.importerRules") }}</h4>
        </div>
      </header>
      <ul>
        <li v-for="rule in selectedImporter.rules" :key="rule">
          {{ rule }}
        </li>
      </ul>
    </section>
  </article>
</template>

<style scoped>
.importer-document {
  padding: 29px 34px 42px;
}
.document-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 22px;
}
.document-header p {
  margin: 0 0 6px;
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 760;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.document-header h3 {
  display: inline;
  margin: 0;
  font-size: 28px;
  letter-spacing: -0.045em;
}
.document-header > div > span {
  margin-left: 10px;
  padding: 5px 8px;
  border-radius: 99px;
  background: color-mix(in srgb, var(--fz-accent) 9%, transparent);
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 780;
  vertical-align: 4px;
}
.document-header > div > span i {
  width: 5px;
  height: 5px;
  display: inline-block;
  margin-right: 4px;
  border-radius: 50%;
  background: currentColor;
}
.document-header > code {
  padding: 6px 8px;
  border-radius: 7px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 10px;
}
.document-description {
  max-width: 720px;
  margin: 13px 0 0;
  font-size: 12px;
  line-height: 1.6;
}
.source-note {
  margin-top: 16px;
  padding: 12px 14px;
  display: flex;
  gap: 10px;
  border-left: 3px solid var(--fz-accent);
  background: color-mix(in srgb, var(--fz-accent) 5%, transparent);
}
.source-note > span {
  color: var(--fz-accent);
  font-size: 15px;
}
.source-note p {
  margin: 0;
  display: grid;
  gap: 3px;
  color: var(--fz-muted);
  font-size: 11px;
  line-height: 1.5;
}
.source-note strong {
  color: var(--fz-ink);
  font-size: 10px;
  text-transform: uppercase;
}
.document-section {
  margin-top: 27px;
}
.document-section > header {
  margin-bottom: 11px;
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
}
.document-section > header > div {
  display: flex;
  align-items: center;
  gap: 9px;
}
.document-section > header p {
  margin: 0;
  color: var(--fz-accent);
  font: 750 10px ui-monospace, monospace;
}
.document-section h4 {
  margin: 0;
  font-size: 15px;
}
.document-section > header > span {
  color: var(--fz-muted);
  font-size: 10px;
}
.format-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.format-grid > div {
  padding: 11px;
  display: flex;
  align-items: flex-start;
  gap: 9px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
}
.format-grid > div > span {
  padding: 4px 6px;
  border-radius: 6px;
  background: var(--fz-surface);
  color: var(--fz-accent);
  font-size: 10px;
  font-weight: 820;
}
.format-grid p {
  margin: 0;
  display: grid;
  gap: 3px;
}
.format-grid strong {
  font-size: 11px;
}
.format-grid small {
  color: var(--fz-muted);
  font-size: 10px;
  line-height: 1.4;
}
.field-table {
  overflow-x: auto;
  border-top: 1px solid var(--fz-line);
}
.field-head,
.field-row {
  min-width: 780px;
  display: grid;
  grid-template-columns: minmax(210px, 0.8fr) minmax(330px, 1.25fr) minmax(160px, 0.6fr);
  gap: 12px;
  align-items: center;
}
.field-head {
  padding: 8px;
  color: var(--fz-muted);
  font-size: 10px;
  text-transform: uppercase;
}
.field-row {
  min-height: 64px;
  padding: 8px;
  border-top: 1px solid var(--fz-line);
}
.field-row > div {
  display: flex;
  align-items: center;
  gap: 7px;
}
.field-row b {
  width: 20px;
  color: var(--fz-muted);
  font-size: 10px;
}
.field-row > div span {
  display: grid;
  gap: 2px;
}
.field-row strong {
  font-size: 11px;
}
.field-row code {
  color: var(--fz-muted);
  font: 600 10px ui-monospace, SFMono-Regular, Menlo, monospace;
}
.field-row > p {
  margin: 0;
  color: var(--fz-muted);
  font-size: 11px;
  line-height: 1.45;
}
.field-row em {
  margin-left: 4px;
  color: var(--fz-accent);
  font-size: 10px;
  font-style: normal;
  font-weight: 760;
  text-transform: uppercase;
}
.field-row > code {
  padding: 6px 7px;
  border-radius: 6px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font-size: 10px;
}
.rules-section ul {
  margin: 0;
  padding: 13px 17px 13px 31px;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  font-size: 11px;
  line-height: 1.7;
}
@media (max-width: 980px) {
  .importer-document {
    padding-inline: 24px;
  }
  .format-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 720px) {
  .importer-document {
    padding: 22px 17px 34px;
  }
  .document-header {
    display: block;
  }
  .document-header > code {
    display: inline-block;
    margin-top: 10px;
  }
  .document-header h3 {
    font-size: 23px;
  }
  .field-head,
  .field-row {
    min-width: 720px;
  }
}
</style>
