<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { registerMessages } from "../../i18n";
import { workspaceMessages } from "../../i18n/workspaceMessages";
registerMessages(workspaceMessages);
import {
  resourceKey,
  type ShareResource,
  type ResourceShare,
  type WorkspaceShares,
} from "./workspaceSharing";
const props = defineProps<{
  data: WorkspaceShares;
  workspaceId: string;
  workspaceName: string;
  busy: boolean;
  error: string;
  status: string;
}>();
const emit = defineEmits<{
  share: [items: ShareResource[], access: string];
  revoke: [share: ResourceShare];
  permission: [share: ResourceShare, access: string];
}>();
const { t } = useI18n();
const board = ref<HTMLElement>();
let focusKey = "";
let focusPending = false;
let focusAction: "share" | "revoke" | "permission" | "all" = "all";
function requestShare(items: ShareResource[]) {
  focusPending = true;
  focusKey = items.length === 1 ? resourceKey(items[0]) : "";
  focusAction = items.length === 1 ? "share" : "all";
  emit("share", items, access.value);
}
function requestRevoke(share: ResourceShare) {
  focusPending = true;
  focusKey = `${share.kind}:${share.resource_id}`;
  focusAction = "revoke";
  emit("revoke", share);
}
function requestPermission(share: ResourceShare, value: string) {
  focusPending = true;
  focusKey = `${share.kind}:${share.resource_id}`;
  focusAction = "permission";
  emit("permission", share, value);
}
watch(
  () => props.busy,
  async (busy, wasBusy) => {
    if (busy || !wasBusy || !focusPending) return;
    focusPending = false;
    if (
      document.activeElement !== document.body &&
      !board.value?.contains(document.activeElement)
    )
      return;
    await nextTick();
    const controls = [
      ...(board.value?.querySelectorAll<HTMLButtonElement | HTMLSelectElement>(
        "[data-resource-key]",
      ) ?? []),
    ].filter(
      (element) =>
        element.dataset.resourceKey === focusKey && !element.disabled,
    );
    const target =
      controls.find((element) =>
        focusAction === "permission"
          ? element.tagName === "SELECT"
          : element.classList.contains(
              focusAction === "revoke" ? "sharing-add" : "sharing-remove",
            ),
      ) ??
      controls[0] ??
      board.value?.querySelector<HTMLElement>(".sharing-status") ??
      board.value?.querySelector<HTMLElement>("input[type=search]");
    target?.focus({ preventScroll: true });
  },
);
const access = ref("read");
const search = ref("");
const canShare = computed(() =>
  props.data.targets.some((item) => item.id === props.workspaceId),
);
const incoming = computed(() =>
  props.data.incoming.filter((item) => item.target_id === props.workspaceId),
);
const available = computed(() => {
  const included = new Set(
    incoming.value.map((item) => `${item.kind}:${item.resource_id}`),
  );
  return props.data.resources.filter(
    (item) =>
      item.workspace_id !== props.workspaceId &&
      !included.has(resourceKey(item)),
  );
});
const ownedShares = computed(
  () => new Set(props.data.outgoing.map((item) => item.id)),
);
const matches = (name: string) =>
  name.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase());
const shownAvailable = computed(() =>
  available.value.filter((item) => matches(item.name)),
);
const shownIncoming = computed(() =>
  incoming.value.filter((item) => matches(item.name)),
);
const native = computed(() =>
  (props.data.native ?? []).filter(
    (item) => item.workspace_id === props.workspaceId,
  ),
);
const shownNative = computed(() =>
  native.value.filter((item) => matches(item.name)),
);
const total = computed(() => incoming.value.length + native.value.length);
</script>

<template>
  <section ref="board" class="sharing-board">
    <header class="sharing-heading">
      <div>
        <h4>{{ t("workspace.shareAssets") }}</h4>
        <p>{{ t("workspace.boardHelp") }}</p>
      </div>
    </header>
    <p v-if="!canShare" class="sharing-notice">
      {{ t("workspace.chooseShared") }}
    </p>
    <div class="sharing-controls">
      <input
        v-model="search"
        type="search"
        :aria-label="t('workspace.searchAssets')"
        :placeholder="t('workspace.searchAssets')"
      />
      <label
        >{{ t("workspace.whenSharing")
        }}<select v-model="access" :disabled="busy || !canShare">
          <option value="read">{{ t("workspace.read") }}</option>
          <option value="edit">{{ t("workspace.edit") }}</option>
        </select></label
      >
    </div>
    <p v-if="error" class="sharing-error" role="alert">{{ error }}</p>
    <p
      v-if="status"
      class="sharing-status"
      tabindex="-1"
      role="status"
      aria-live="polite"
    >
      {{ status }}
    </p>
    <div class="sharing-columns">
      <div class="sharing-column sharing-available">
        <header>
          <div>
            <h5>
              {{ t("workspace.yourAssets") }}
              <span class="sharing-count">{{ available.length }}</span>
            </h5>
            <p>{{ t("workspace.availableHelp") }}</p>
          </div>
          <button
            class="share-all"
            type="button"
            :disabled="busy || !canShare || !available.length"
            @click="requestShare(available)"
          >
            {{ t("workspace.shareAll") }} <span aria-hidden="true">→</span>
          </button>
        </header>
        <ul :aria-label="t('workspace.yourAssets')" class="sharing-list">
          <li v-for="item in shownAvailable" :key="resourceKey(item)">
            <button
              class="sharing-add"
              :data-resource-key="resourceKey(item)"
              type="button"
              :disabled="busy || !canShare"
              :aria-label="t('workspace.shareAsset', { name: item.name })"
              @click="requestShare([item])"
            >
              <span class="sharing-kind" aria-hidden="true">{{
                t(`workspace.kindMarks.${item.kind}`)
              }}</span>
              <span class="sharing-resource"
                ><strong>{{ item.name }}</strong
                ><small
                  >{{ t(`workspace.kinds.${item.kind}`)
                  }}<template v-if="item.workspace_name">
                    · {{ item.workspace_name }}</template
                  ></small
                ></span
              >
              <span class="sharing-arrow" aria-hidden="true">→</span>
            </button>
          </li>
          <li v-if="!shownAvailable.length" class="sharing-empty">
            {{
              t(
                search
                  ? "workspace.noMatches"
                  : available.length
                    ? "workspace.noMatches"
                    : "workspace.noneAvailable",
              )
            }}
          </li>
        </ul>
      </div>
      <div class="sharing-column sharing-included">
        <header>
          <div>
            <h5>
              {{ t("workspace.inWorkspace", { name: workspaceName }) }}
              <span class="sharing-count">{{ total }}</span>
            </h5>
            <p>{{ t("workspace.includedHelp") }}</p>
          </div>
        </header>
        <ul
          :aria-label="t('workspace.inWorkspace', { name: workspaceName })"
          class="sharing-list"
        >
          <li
            v-for="share in shownIncoming"
            :key="share.id"
            class="sharing-included-row"
          >
            <button
              v-if="ownedShares.has(share.id)"
              type="button"
              class="sharing-remove"
              :data-resource-key="`${share.kind}:${share.resource_id}`"
              :disabled="busy"
              :aria-label="t('workspace.stopSharing', { name: share.name })"
              @click="requestRevoke(share)"
            >
              <span aria-hidden="true">←</span>
            </button>
            <span v-else class="sharing-other-mark" aria-hidden="true">↳</span>
            <span class="sharing-resource"
              ><strong>{{ share.name }}</strong
              ><small>{{
                t(
                  ownedShares.has(share.id)
                    ? `workspace.kinds.${share.kind}`
                    : "workspace.fromMember",
                )
              }}</small></span
            >
            <select
              v-if="ownedShares.has(share.id)"
              :data-resource-key="`${share.kind}:${share.resource_id}`"
              :value="share.access"
              :disabled="busy || !canShare"
              :aria-label="t('workspace.assetPermission', { name: share.name })"
              @change="
                requestPermission(
                  share,
                  ($event.target as HTMLSelectElement).value,
                )
              "
            >
              <option value="read">{{ t("workspace.read") }}</option>
              <option value="edit">{{ t("workspace.edit") }}</option>
            </select>
            <small v-else class="sharing-access">{{
              t(`workspace.${share.access}`)
            }}</small>
          </li>
          <li
            v-for="item in shownNative"
            :key="resourceKey(item)"
            class="sharing-included-row"
          >
            <span class="sharing-other-mark" aria-hidden="true">·</span
            ><span class="sharing-resource"
              ><strong>{{ item.name }}</strong
              ><small>{{ t(`workspace.kinds.${item.kind}`) }}</small></span
            ><small class="sharing-access">{{
              t("workspace.nativeAsset")
            }}</small>
          </li>
          <li
            v-if="!shownIncoming.length && !shownNative.length"
            class="sharing-empty"
          >
            {{ t(search ? "workspace.noMatches" : "workspace.noneIncluded") }}
          </li>
        </ul>
      </div>
    </div>
    <p class="sharing-footnote">{{ t("workspace.transferHelp") }}</p>
  </section>
</template>

<style scoped>
.sharing-board {
  container-type: inline-size;
  padding-block: 22px;
  border-bottom: 1px solid var(--fz-line);
}
.sharing-heading h4 {
  margin: 0;
  font-size: 15px;
  letter-spacing: -0.025em;
}
.sharing-heading p,
.sharing-footnote {
  margin: 5px 0 0;
  color: var(--fz-muted);
  font-size: 11px;
  line-height: 1.6;
}
.sharing-notice {
  padding: 10px 12px;
  background: var(--fz-surface-soft);
  border-radius: 8px;
  font-size: 11px;
}
.sharing-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-block: 16px 12px;
}
.sharing-controls input {
  flex: 1 1 160px;
  min-width: 0;
}
.sharing-controls label {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--fz-muted);
  font-size: 10px;
}
input,
select,
button {
  font: inherit;
  color: var(--fz-ink);
}
input,
select {
  background: var(--fz-surface);
  border: 1px solid var(--fz-line);
  border-radius: 7px;
  padding: 8px;
  font-size: 11px;
}
button {
  cursor: pointer;
}
button:disabled {
  cursor: default;
  opacity: 0.45;
}
.sharing-columns {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
}
.sharing-column {
  min-width: 0;
  border: 1px solid var(--fz-line);
  border-radius: 12px;
  overflow: hidden;
  background: var(--fz-surface);
}
.sharing-column > header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 76px;
  padding: 12px;
  border-bottom: 1px solid var(--fz-line);
  background: var(--fz-surface-soft);
}
.sharing-column > header > div {
  flex: 1;
  min-width: 0;
}
h5 {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.sharing-column header p {
  margin: 3px 0 0;
  font-size: 10px;
  color: var(--fz-muted);
}
.sharing-included {
  border-top: 2px solid var(--fz-accent);
}
.sharing-count {
  display: inline-block;
  margin-left: 4px;
  padding: 0 5px;
  border-radius: 5px;
  color: var(--fz-muted);
  background: var(--fz-surface);
  font-variant-numeric: tabular-nums;
  font-size: 10px;
}
.share-all {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 5px 0;
  background: transparent;
  color: var(--fz-accent);
  border: 0;
  font-size: 10px;
  font-weight: 750;
  white-space: nowrap;
}
.sharing-list {
  min-height: 180px;
  max-height: 340px;
  overflow-y: auto;
  margin: 0;
  padding: 5px;
  list-style: none;
}
.sharing-list li {
  border-bottom: 1px solid var(--fz-line);
}
.sharing-list li:last-child {
  border: 0;
}
.sharing-add,
.sharing-included-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 7px;
  width: 100%;
  min-width: 0;
  text-align: left;
}
.sharing-add {
  border: 0;
  border-radius: 7px;
  background: transparent;
}
.sharing-add:hover:not(:disabled) {
  background: var(--fz-accent-soft);
}
.sharing-kind {
  display: grid;
  place-items: center;
  width: 26px;
  height: 28px;
  flex-shrink: 0;
  border: 1px solid var(--fz-line);
  border-radius: 6px;
  color: var(--fz-muted);
  font-size: 9px;
  font-weight: 750;
}
.sharing-resource {
  min-width: 0;
  flex: 1;
}
.sharing-resource strong {
  display: block;
  font-size: 11px;
  font-weight: 650;
  overflow-wrap: anywhere;
  line-height: 1.4;
}
.sharing-resource small {
  display: block;
  font-size: 10px;
  color: var(--fz-muted);
  margin-top: 3px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.sharing-arrow {
  color: var(--fz-accent);
  font-size: 17px;
}
.sharing-remove {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 25px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 6px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
}
.sharing-remove:hover:not(:disabled) {
  color: var(--fz-ink);
  border-color: var(--fz-accent);
}
.sharing-other-mark {
  width: 25px;
  flex-shrink: 0;
  color: var(--fz-muted);
  text-align: center;
}
.sharing-included-row select {
  max-width: 104px;
  padding: 5px 3px;
  font-size: 10px;
}
.sharing-access {
  color: var(--fz-muted);
  font-size: 9px;
  max-width: 70px;
}
.sharing-list .sharing-empty {
  display: grid;
  place-items: center;
  padding: 30px 18px;
  min-height: 160px;
  text-align: center;
  color: var(--fz-muted);
  font-size: 11px;
  line-height: 1.7;
  border: 0;
}
.sharing-error {
  padding: 10px;
  border-left: 3px solid var(--fz-negative);
  font-size: 11px;
}
.sharing-status {
  font-size: 11px;
  color: var(--fz-accent);
}
@container (max-width: 430px) {
  .sharing-columns {
    grid-template-columns: minmax(0, 1fr);
  }
  .sharing-list {
    max-height: 260px;
    min-height: 130px;
  }
  .sharing-list .sharing-empty {
    min-height: 120px;
    padding: 20px;
  }
}
</style>
