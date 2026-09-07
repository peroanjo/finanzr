import { computed } from "vue";
import { i18n } from "./i18n";

const rawVersion = import.meta.env.VITE_FINANZR_VERSION?.trim();
const rawCommit = import.meta.env.VITE_FINANZR_COMMIT?.trim();
const rawDeployedAt = import.meta.env.VITE_FINANZR_DEPLOYED_AT?.trim();

export const buildCommit = computed(
  () => rawCommit || i18n.global.t("shared.buildInfo.development"),
);

export const buildDate = computed(() => {
  if (!rawDeployedAt) return i18n.global.t("shared.buildInfo.localEnvironment");
  const date = new Date(rawDeployedAt);
  if (Number.isNaN(date.getTime())) return rawDeployedAt;
  return new Intl.DateTimeFormat(i18n.global.locale.value, {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Europe/Madrid",
  }).format(date);
});

export const buildLabel = computed(
  () =>
    `${rawVersion ? `v${rawVersion}` : i18n.global.t("shared.buildInfo.development")} · ${buildCommit.value} · ${buildDate.value}`,
);
