<script lang="ts">
export type AssetReturnMode = "percent" | "pnl";
</script>

<script setup lang="ts">
import { useI18n } from "vue-i18n";

const mode = defineModel<AssetReturnMode>({ required: true });
const { t } = useI18n();
</script>

<template>
  <div class="asset-return-control">
    <span>{{ t("shared.assetReturnToggle.label") }}</span>
    <div role="group" :aria-label="t('shared.assetReturnToggle.groupAria')">
      <button
        type="button"
        :class="{ active: mode === 'percent' }"
        :aria-pressed="mode === 'percent'"
        :aria-label="t('shared.assetReturnToggle.percentAria')"
        @click="mode = 'percent'"
      >
        %
      </button>
      <button
        type="button"
        :class="{ active: mode === 'pnl' }"
        :aria-pressed="mode === 'pnl'"
        :aria-label="t('shared.assetReturnToggle.pnlAria')"
        @click="mode = 'pnl'"
      >
        P&amp;L
      </button>
    </div>
  </div>
</template>

<style scoped>
.asset-return-control {
  display: grid;
  justify-items: end;
  gap: 5px;
  color: var(--fz-muted);
}
.asset-return-control > span {
  font-size: 10px;
  font-weight: 710;
}
.asset-return-control > div {
  padding: 2px;
  display: flex;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: var(--fz-surface-soft);
}
.asset-return-control button {
  min-width: 29px;
  height: 23px;
  padding: 0 6px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--fz-muted);
  font: inherit;
  font-size: 10px;
  font-weight: 780;
  cursor: pointer;
}
.asset-return-control button.active {
  background: var(--fz-surface);
  color: var(--fz-ink);
  box-shadow: 0 2px 7px rgba(7, 16, 11, 0.1);
}
.asset-return-control button:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 1px;
}
</style>
