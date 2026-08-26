<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { api } from "../api/client";
import type { ApiRow } from "../types/api";

const props = defineProps<{
  endpoint: string;
  accountsEndpoint: string;
  compact?: boolean;
  accountId?: string;
  accept?: string;
  fileHint?: string;
  hideAccountSelector?: boolean;
}>();
const emit = defineEmits<{ imported: [] }>();
const { t } = useI18n();
const accounts = ref<ApiRow[]>([]);
const account = ref(props.accountId ?? "");
const file = ref<File>();
const message = ref("");
const messageKind = ref<"success" | "error" | "">("");
const busy = ref(false);

function selectPreferredAccount() {
  if (props.hideAccountSelector && props.accountId) {
    account.value = props.accountId;
    return;
  }
  const preferred = accounts.value.find(
    (item) => String(item.id) === props.accountId,
  );
  if (preferred) account.value = String(preferred.id);
  else if (!accounts.value.some((item) => String(item.id) === account.value)) {
    account.value = accounts.value.length ? String(accounts.value[0].id) : "";
  }
}

onMounted(async () => {
  if (props.hideAccountSelector && props.accountId) return;
  accounts.value = await api<ApiRow[]>(props.accountsEndpoint);
  selectPreferredAccount();
});
watch(() => props.accountId, selectPreferredAccount);

function choose(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0];
  message.value = "";
  messageKind.value = "";
}

async function upload() {
  if (!file.value || !account.value) return;
  busy.value = true;
  message.value = "";
  messageKind.value = "";
  const body = new FormData();
  body.append("file", file.value);
  body.append("cuenta_id", account.value);
  try {
    const result = await api<{ imported: number; skipped: number }>(
      props.endpoint,
      { method: "POST", body },
    );
    message.value = t("shared.importPanel.result", result);
    messageKind.value = "success";
    emit("imported");
  } catch (reason) {
    message.value =
      reason instanceof Error
        ? reason.message
        : t("shared.importPanel.importError");
    messageKind.value = "error";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <form
    class="import"
    :class="{ 'import-compact': compact }"
    @submit.prevent="upload"
  >
    <h2 v-if="!compact">{{ t("shared.importPanel.title") }}</h2>
    <label v-if="!hideAccountSelector" class="import-control">
      <span>{{ t("shared.importPanel.destinationAccount") }}</span>
      <select
        v-model="account"
        :aria-label="t('shared.importPanel.destinationAccount')"
        required
      >
        <option
          v-for="item in accounts"
          :key="String(item.id)"
          :value="String(item.id)"
        >
          {{ item.nombre }}
        </option>
      </select>
    </label>

    <label class="import-file" :class="{ selected: file }">
      <input type="file" :accept="accept" required @change="choose" />
      <span class="import-file-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24">
          <path
            d="M12 3v11m0-11 4 4m-4-4L8 7M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4"
          />
        </svg>
      </span>
      <span class="import-file-copy">
        <strong>{{
          file?.name ?? t("shared.importPanel.selectStatement")
        }}</strong>
        <small>{{
          file
            ? t("shared.importPanel.fileReady")
            : (fileHint ?? t("shared.importPanel.dropOrBrowse"))
        }}</small>
      </span>
      <span class="import-file-action">{{
        file
          ? t("shared.importPanel.change")
          : t("shared.importPanel.chooseFile")
      }}</span>
    </label>

    <button class="import-submit" :disabled="busy || !file || !account">
      <span aria-hidden="true">↗</span>
      {{
        busy
          ? t("shared.importPanel.importing")
          : t("shared.importPanel.importStatement")
      }}
    </button>
    <p
      v-if="message"
      class="import-message"
      :class="messageKind"
      :role="messageKind === 'error' ? 'alert' : 'status'"
      aria-live="polite"
    >
      {{ message }}
    </p>
  </form>
</template>
