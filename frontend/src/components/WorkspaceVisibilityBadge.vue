<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { registerMessages } from "../i18n";
import { workspaceMessages } from "../i18n/workspaceMessages";

defineProps<{ shared: boolean; sidebar?: boolean }>();
registerMessages(workspaceMessages);
const { t } = useI18n();
</script>

<template>
  <span
    class="workspace-visibility"
    :class="{ shared, private: !shared, sidebar }"
  >
    <i aria-hidden="true" />{{
      t(shared ? "workspace.shared" : "workspace.private")
    }}
  </span>
</template>

<style scoped>
.workspace-visibility {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: fit-content;
  padding: 3px 8px;
  border: 1px solid var(--fz-workspace-private-border, #b4d9c3);
  border-radius: 999px;
  background: var(--fz-workspace-private-bg, #e8f5ed);
  color: var(--fz-workspace-private-ink, #14643f);
  font-size: 10px;
  font-weight: 750;
  line-height: 1.5;
  white-space: nowrap;
}
.workspace-visibility i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.shared {
  border-color: var(--fz-workspace-shared-border, #b8cdf0);
  background: var(--fz-workspace-shared-bg, #eaf1ff);
  color: var(--fz-workspace-shared-ink, #2458a6);
}
.sidebar.private {
  border-color: #38785c;
  background: #193b2b;
  color: #a6e4c7;
}
.sidebar.shared {
  border-color: #405a80;
  background: #203650;
  color: #adcfff;
}
</style>
