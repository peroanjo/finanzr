<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { api } from "../../api/client";
import { registerMessages } from "../../i18n";
import { versionMessages } from "../../i18n/versionMessages";

registerMessages(versionMessages);
const { t, locale } = useI18n();
interface VersionStatus {
  installed_version: string;
  installed_commit: string | null;
  comparison_basis: string;
  repository_url: string;
  checked_at: string;
  release_status: string;
  release_update: string;
  latest_release: string | null;
  releases: {
    tag: string;
    name: string;
    published_at: string;
    prerelease: boolean;
    notes: string;
    url: string;
  }[];
  main: {
    status: string;
    ahead_by: number;
    behind_by: number;
    url: string;
    commits: { sha: string; message: string; url: string }[];
  } | null;
}
const status = ref<VersionStatus>();
const busy = ref(false);
const failed = ref(false);
function date(value: string) {
  return new Date(value).toLocaleString(locale.value);
}
async function load() {
  busy.value = true;
  failed.value = false;
  try {
    status.value = await api<VersionStatus>("/installation/version");
  } catch {
    failed.value = true;
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>

<template>
  <article class="version-panel" :aria-busy="busy">
    <header>
      <div>
        <p>Git · main</p>
        <h3>{{ t("version.title") }}</h3>
      </div>
      <button type="button" :disabled="busy" @click="load">
        {{ t(busy ? "version.loading" : "version.check") }}
      </button>
    </header>
    <p class="muted">{{ t("version.help") }}</p>
    <p v-if="failed" role="alert">{{ t("version.error") }}</p>
    <template v-if="status">
      <section>
        <h4>{{ t("version.installed") }}</h4>
        <strong>{{ status.installed_version }}</strong>
        <code v-if="status.installed_commit">{{
          status.installed_commit
        }}</code>
        <p v-else class="muted">{{ t("version.tagBasis") }}</p>
        <p v-if="status.latest_release">
          {{ t("version.latest") }}:
          <strong>{{ status.latest_release }}</strong>
        </p>
        <p role="status">{{ t(`version.update.${status.release_update}`) }}</p>
        <p class="muted">
          {{ t("version.checked", { date: date(status.checked_at) }) }}
        </p>
        <a
          :href="status.repository_url"
          target="_blank"
          rel="noopener noreferrer"
          >{{ t("version.repository") }} ↗</a
        >
      </section>
      <section>
        <h4>{{ t("version.main") }}</h4>
        <template v-if="status.main">
          <p v-if="status.main.status === 'ahead'">
            {{ t("version.newCommits", { count: status.main.ahead_by }) }}
          </p>
          <p v-else>{{ t(`version.branch.${status.main.status}`) }}</p>
          <a :href="status.main.url" target="_blank" rel="noopener noreferrer"
            >{{ t("version.compare") }} ↗</a
          >
          <ul>
            <li v-for="commit in status.main.commits" :key="commit.sha">
              <a :href="commit.url" target="_blank" rel="noopener noreferrer"
                ><code>{{ commit.sha.slice(0, 7) }}</code>
                {{ commit.message }}</a
              >
            </li>
          </ul>
          <p
            v-if="status.main.ahead_by > status.main.commits.length"
            class="muted"
          >
            {{ t("version.moreCommits") }}
          </p>
        </template>
        <p v-else role="status">{{ t("version.comparisonUnavailable") }}</p>
      </section>
      <section>
        <h4>{{ t("version.changelog") }}</h4>
        <p class="muted">{{ t("version.releaseLimit") }}</p>
        <p v-if="status.release_status === 'unavailable'" role="status">
          {{ t("version.error") }}
        </p>
        <p v-else-if="!status.releases.length">{{ t("version.noReleases") }}</p>
        <details
          v-for="(release, index) in status.releases"
          :key="release.tag"
          :open="index === 0"
        >
          <summary>
            <strong>{{ release.tag }}</strong>
            <span v-if="release.prerelease" class="badge">{{
              t("version.prerelease")
            }}</span
            ><small>{{ date(release.published_at) }}</small>
          </summary>
          <h5>{{ release.name }}</h5>
          <p class="release-notes">
            {{ release.notes || t("version.noNotes") }}
          </p>
          <a :href="release.url" target="_blank" rel="noopener noreferrer"
            >{{ t("version.openRelease") }} ↗</a
          >
        </details>
      </section>
    </template>
  </article>
</template>

<style scoped>
.version-panel {
  padding: 28px;
  font-size: 12px;
  line-height: 1.6;
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
h3,
h4,
h5,
header p {
  margin: 0;
}
header p,
.muted,
small {
  color: var(--fz-muted);
}
h3 {
  font-size: 22px;
}
h4 {
  margin-bottom: 10px;
  font-size: 15px;
}
section {
  padding-block: 22px;
  border-bottom: 1px solid var(--fz-line);
}
button {
  padding: 9px 12px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  cursor: pointer;
}
button:disabled {
  cursor: wait;
  opacity: 0.6;
}
a {
  color: var(--fz-accent);
  overflow-wrap: anywhere;
}
code {
  overflow-wrap: anywhere;
}
section > code {
  display: block;
  margin-top: 8px;
}
ul {
  padding-left: 18px;
}
li + li {
  margin-top: 8px;
}
details {
  margin-top: 14px;
  padding: 14px;
  border: 1px solid var(--fz-line);
  border-radius: 12px;
}
summary {
  cursor: pointer;
}
small {
  display: block;
  margin-top: 4px;
}
.badge {
  padding: 2px 6px;
  border-radius: 6px;
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
}
.release-notes {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
