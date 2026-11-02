<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import WorkspaceVisibilityBadge from "../WorkspaceVisibilityBadge.vue";
import { useI18n } from "vue-i18n";
import { registerMessages } from "../../i18n";
import { workspaceMessages } from "../../i18n/workspaceMessages";
import { api, json } from "../../api/client";
import { useSessionStore } from "../../stores/session";
import type { UserSession } from "../../types/api";

interface Member {
  id: string;
  name: string;
  email: string;
  role: string;
  is_self: boolean;
}
interface Settings {
  id: string;
  name: string;
  is_personal: boolean;
  role: string;
  members: Member[];
  invitations: { id: string; email: string; role: string }[];
}
interface Resource {
  kind: string;
  id: string;
  name: string;
  workspace_id: string;
}
interface Share {
  id: string;
  kind: string;
  resource_id: string;
  name: string;
  target_id: string;
  target_name: string;
  access: string;
}
interface Shares {
  resources: Resource[];
  targets: { id: string; name: string }[];
  outgoing: Share[];
  incoming: Share[];
}
registerMessages(workspaceMessages);
const { t } = useI18n();
const session = useSessionStore();
const settings = ref<Settings>();
const shares = ref<Shares>();
const busy = ref(false);
const error = ref("");
const name = ref("");
const dialog = ref<HTMLDialogElement>();
const dialogInput = ref<HTMLInputElement>();
const dialogMode = ref<"create" | "join">("create");
const dialogValue = ref("");
const dialogError = ref("");
const workspaceOptions = computed(
  () =>
    session.user?.workspaces ??
    (settings.value
      ? [
          {
            id: settings.value.id,
            name: settings.value.name,
            is_shared: settings.value.members.length > 1,
          },
        ]
      : []),
);
const selectedWorkspace = computed(() =>
  settings.value
    ? {
        id: settings.value.id,
        name: settings.value.name,
        is_shared: settings.value.members.length > 1,
      }
    : workspaceOptions.value.find(
        (item) => item.id === session.user?.active_workspace_id,
      ),
);
const workspaceInitial = computed(
  () =>
    selectedWorkspace.value?.name.trim().slice(0, 1).toLocaleUpperCase() ?? "",
);
async function openDialog(mode: "create" | "join") {
  dialogMode.value = mode;
  dialogValue.value = "";
  dialogError.value = "";
  dialog.value?.showModal();
  await nextTick();
  dialogInput.value?.focus();
}
function closeDialog() {
  if (!busy.value) dialog.value?.close();
}
async function submitDialog() {
  if (busy.value || !dialogValue.value.trim()) return;
  busy.value = true;
  dialogError.value = "";
  try {
    await apply(
      api<UserSession>(
        dialogMode.value === "create"
          ? "/workspaces"
          : "/workspaces/invitations/accept",
        json(
          "POST",
          dialogMode.value === "create"
            ? { name: dialogValue.value.trim() }
            : { token: dialogValue.value.trim() },
        ),
      ),
    );
    dialog.value?.close();
    await load();
  } catch (reason) {
    dialogError.value =
      reason instanceof Error ? reason.message : t("workspace.failure");
  } finally {
    busy.value = false;
  }
}
const email = ref("");
const inviteRole = ref("editor");
const invitationCode = ref("");
const selectedResource = ref("");
const targetId = ref("");
const access = ref("read");
const confirmArchive = ref(false);
const resource = computed(() =>
  shares.value?.resources.find(
    (item) => `${item.kind}:${item.id}` === selectedResource.value,
  ),
);
const targets = computed(
  () =>
    shares.value?.targets.filter(
      (item) => item.id !== resource.value?.workspace_id,
    ) ?? [],
);
async function load() {
  [settings.value, shares.value] = await Promise.all([
    api<Settings>("/workspaces/settings"),
    api<Shares>("/workspaces/shares"),
  ]);
  name.value = settings.value.name;
}
async function run(action: () => Promise<unknown>) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await action();
    await load();
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : t("workspace.failure");
  } finally {
    busy.value = false;
  }
}
async function apply(response: Promise<UserSession>) {
  session.applySession(await response);
  localStorage.setItem("finanzr-workspace-revision", String(Date.now()));
}
function rename() {
  return run(() =>
    api("/workspaces/settings", json("PATCH", { name: name.value })).then(() =>
      session.restore(),
    ),
  );
}
function invite() {
  return run(async () => {
    const result = await api<{ token: string }>(
      "/workspaces/invitations",
      json("POST", { email: email.value, role: inviteRole.value }),
    );
    invitationCode.value = result.token;
    email.value = "";
  });
}
function memberRole(member: Member, role: string) {
  return run(() =>
    apply(
      api<UserSession>(
        `/workspaces/members/${member.id}`,
        json("PATCH", { role }),
      ),
    ),
  );
}
function removeMember(member: Member) {
  return run(() =>
    apply(
      api<UserSession>(`/workspaces/members/${member.id}`, {
        method: "DELETE",
      }),
    ),
  );
}
function grant() {
  return run(() =>
    api(
      "/workspaces/shares",
      json("POST", {
        kind: resource.value?.kind,
        resource_id: resource.value?.id,
        target_id: targetId.value,
        access: access.value,
      }),
    ),
  );
}
function revoke(share: Share) {
  return run(() => api(`/workspaces/shares/${share.id}`, { method: "DELETE" }));
}
onMounted(() => run(async () => {}));
</script>

<template>
  <article class="workspace-panel" :aria-busy="busy">
    <header>
      <p>{{ t("workspace.subtitle") }}</p>
      <h3>{{ t("workspace.title") }}</h3>
    </header>
    <div class="workspace-toolbar">
      <label
        class="workspace-selection"
        :class="{
          'is-shared': selectedWorkspace?.is_shared,
          'is-disabled': busy || session.switchingWorkspace || !settings,
        }"
      >
        <span class="workspace-selection-face" aria-hidden="true">
          <span class="workspace-monogram">{{ workspaceInitial || "·" }}</span>
          <span class="workspace-selection-copy">
            <span class="workspace-selection-caption">{{
              t("workspace.activeSpace")
            }}</span>
            <span class="workspace-selection-name">{{
              selectedWorkspace?.name ?? t("workspace.loading")
            }}</span>
          </span>
          <WorkspaceVisibilityBadge
            v-if="selectedWorkspace"
            :shared="Boolean(selectedWorkspace.is_shared)"
          />
          <svg class="workspace-switch-icon" viewBox="0 0 20 20" fill="none">
            <path d="m7 7 3-3 3 3M7 13l3 3 3-3" />
          </svg>
        </span>
        <select
          :aria-label="t('workspace.configuring')"
          :value="settings?.id ?? session.user?.active_workspace_id ?? ''"
          :disabled="busy || session.switchingWorkspace || !settings"
          @change="
            run(() =>
              session.selectWorkspace(
                ($event.target as HTMLSelectElement).value,
              ),
            )
          "
        >
          <option
            v-for="item in workspaceOptions"
            :key="item.id"
            :value="item.id"
          >
            {{ item.name }} ·
            {{ t(item.is_shared ? "workspace.shared" : "workspace.private") }}
          </option>
        </select>
      </label>
      <div class="workspace-actions">
        <button
          class="workspace-create"
          type="button"
          :disabled="busy"
          @click="openDialog('create')"
        >
          <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M10 4v12M4 10h12" />
          </svg>
          {{ t("workspace.create") }}
        </button>
        <button
          class="workspace-join"
          type="button"
          :disabled="busy"
          @click="openDialog('join')"
        >
          <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path
              d="M11 3h4a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-4M3 10h9m-3-3 3 3-3 3"
            />
          </svg>
          {{ t("workspace.join") }}
        </button>
      </div>
    </div>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="busy" role="status">{{ t("workspace.loading") }}</p>
    <section v-if="settings">
      <h4 class="workspace-heading">
        <span>{{ settings.name }}</span>
        <WorkspaceVisibilityBadge :shared="settings.members.length > 1" />
      </h4>
      <p>{{ t("workspace.scopeHelp") }}</p>
      <form
        v-if="!settings.is_personal && settings.role === 'owner'"
        @submit.prevent="rename"
      >
        <label
          >{{ t("workspace.name")
          }}<input v-model="name" required maxlength="120" /></label
        ><button :disabled="busy">{{ t("workspace.rename") }}</button>
      </form>
      <h4>{{ t("workspace.members") }}</h4>
      <ul>
        <li v-for="member in settings.members" :key="member.id">
          <span
            >{{ member.name || member.email }}
            <small>{{ member.email }}</small></span
          >
          <select
            v-if="!settings.is_personal && settings.role === 'owner'"
            :value="member.role"
            :disabled="busy"
            :aria-label="
              t('workspace.memberRole', { name: member.name || member.email })
            "
            @change="
              memberRole(member, ($event.target as HTMLSelectElement).value)
            "
          >
            <option
              v-for="role in ['owner', 'editor', 'viewer']"
              :key="role"
              :value="role"
            >
              {{ t(`workspace.roles.${role}`) }}
            </option>
          </select>
          <small v-else>{{ t(`workspace.roles.${member.role}`) }}</small>
          <button
            v-if="
              !settings.is_personal &&
              (settings.role === 'owner' || member.is_self)
            "
            type="button"
            :disabled="busy"
            @click="removeMember(member)"
          >
            {{ t(member.is_self ? "workspace.leave" : "workspace.remove") }}
          </button>
        </li>
      </ul>
      <template v-if="!settings.is_personal && settings.role === 'owner'">
        <form @submit.prevent="invite">
          <label
            >{{ t("workspace.inviteEmail")
            }}<input v-model="email" type="email" required /></label
          ><label
            >{{ t("workspace.permission")
            }}<select v-model="inviteRole">
              <option value="editor">{{ t("workspace.roles.editor") }}</option>
              <option value="viewer">{{ t("workspace.roles.viewer") }}</option>
            </select></label
          ><button :disabled="busy">{{ t("workspace.invite") }}</button>
        </form>
        <p v-if="invitationCode" role="status">
          {{ t("workspace.inviteCreated")
          }}<code class="invitation-code">{{ invitationCode }}</code>
        </p>
        <ul>
          <li v-for="invitation in settings.invitations" :key="invitation.id">
            <span
              >{{ invitation.email }} ·
              {{ t(`workspace.roles.${invitation.role}`) }}</span
            ><button
              type="button"
              :disabled="busy"
              @click="
                run(() =>
                  api(`/workspaces/invitations/${invitation.id}`, {
                    method: 'DELETE',
                  }),
                )
              "
            >
              {{ t("workspace.cancelInvite") }}
            </button>
          </li>
        </ul>
      </template>
    </section>
    <section v-if="shares">
      <h4>{{ t("workspace.shareAssets") }}</h4>
      <p>{{ t("workspace.shareHelp") }}</p>
      <form @submit.prevent="grant">
        <label
          >{{ t("workspace.resource")
          }}<select v-model="selectedResource" required>
            <option disabled value="">{{ t("workspace.choose") }}</option>
            <option
              v-for="item in shares.resources"
              :key="`${item.kind}:${item.id}`"
              :value="`${item.kind}:${item.id}`"
            >
              {{ item.name }} · {{ t(`workspace.kinds.${item.kind}`) }}
            </option>
          </select></label
        >
        <label
          >{{ t("workspace.target")
          }}<select v-model="targetId" required>
            <option disabled value="">{{ t("workspace.choose") }}</option>
            <option
              v-for="target in targets"
              :key="target.id"
              :value="target.id"
            >
              {{ target.name }}
            </option>
          </select></label
        >
        <label
          >{{ t("workspace.permission")
          }}<select v-model="access">
            <option value="read">{{ t("workspace.read") }}</option>
            <option value="edit">{{ t("workspace.edit") }}</option>
          </select></label
        >
        <button
          :disabled="
            busy || !resource || !targets.some((item) => item.id === targetId)
          "
        >
          {{ t("workspace.share") }}
        </button>
      </form>
      <h4>{{ t("workspace.outgoing") }}</h4>
      <ul>
        <li v-for="share in shares.outgoing" :key="share.id">
          <span
            >{{ share.name }} → {{ share.target_name
            }}<small>{{ t(`workspace.${share.access}`) }}</small></span
          ><button :disabled="busy" type="button" @click="revoke(share)">
            {{ t("workspace.revoke") }}
          </button>
        </li>
      </ul>
      <h4>{{ t("workspace.incoming") }}</h4>
      <ul>
        <li v-for="share in shares.incoming" :key="share.id">
          <span>{{ share.name }}</span
          ><small>{{ t(`workspace.${share.access}`) }}</small>
        </li>
      </ul>
    </section>
    <section
      v-if="settings && !settings.is_personal && settings.role === 'owner'"
    >
      <h4>{{ t("workspace.archive") }}</h4>
      <p>{{ t("workspace.archiveHelp") }}</p>
      <label class="confirmation"
        ><input v-model="confirmArchive" type="checkbox" />{{
          t("workspace.archiveConfirm")
        }}</label
      >
      <button
        :disabled="busy || !confirmArchive"
        type="button"
        @click="
          run(() =>
            apply(
              api<UserSession>('/workspaces/settings', { method: 'DELETE' }),
            ),
          )
        "
      >
        {{ t("workspace.archive") }}
      </button>
    </section>
    <dialog
      ref="dialog"
      class="workspace-action-dialog"
      aria-modal="true"
      aria-labelledby="workspace-action-title"
      :aria-busy="busy"
      @cancel.prevent="closeDialog"
      @keydown.stop
      @click.self="closeDialog"
    >
      <div class="workspace-dialog-body">
        <header class="workspace-dialog-header">
          <h3 id="workspace-action-title">
            {{
              t(dialogMode === "create" ? "workspace.create" : "workspace.join")
            }}
          </h3>
          <button
            type="button"
            :disabled="busy"
            :aria-label="t('common.close')"
            @click="closeDialog"
          >
            ×
          </button>
        </header>
        <p id="workspace-action-help">
          {{
            t(
              dialogMode === "create"
                ? "workspace.createHelp"
                : "workspace.joinHelp",
            )
          }}
        </p>
        <form @submit.prevent="submitDialog">
          <label
            >{{
              t(
                dialogMode === "create"
                  ? "workspace.name"
                  : "workspace.invitationCode",
              )
            }}
            <input
              ref="dialogInput"
              v-model="dialogValue"
              :disabled="busy"
              required
              :maxlength="dialogMode === 'create' ? 120 : undefined"
              autocomplete="off"
              aria-describedby="workspace-action-help"
            />
          </label>
          <p v-if="dialogError" role="alert">{{ dialogError }}</p>
          <footer>
            <button type="button" :disabled="busy" @click="closeDialog">
              {{ t("common.cancel") }}
            </button>
            <button type="submit" :disabled="busy || !dialogValue.trim()">
              {{
                t(
                  busy
                    ? "workspace.loading"
                    : dialogMode === "create"
                      ? "workspace.create"
                      : "workspace.join",
                )
              }}
            </button>
          </footer>
        </form>
      </div>
    </dialog>
  </article>
</template>

<style scoped>
.workspace-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}
.workspace-panel {
  container-type: inline-size;
  padding: 28px;
  font-size: 12px;
  line-height: 1.6;
}
header p,
small {
  color: var(--fz-muted);
}
h3 {
  font-size: 22px;
  margin: 0;
}
h4 {
  font-size: 15px;
  margin: 8px 0;
}
section {
  padding-block: 18px;
  border-bottom: 1px solid var(--fz-line);
}
form {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 10px;
  margin-block: 15px;
}
label {
  display: grid;
  gap: 5px;
  flex: 1;
  min-width: 130px;
}
input,
select,
button {
  max-width: 100%;
  padding: 9px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: var(--fz-surface-soft);
  color: var(--fz-ink);
  font: inherit;
}
button {
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
ul {
  list-style: none;
  padding: 0;
}
li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding-block: 9px;
}
li > span {
  flex: 1;
  overflow-wrap: anywhere;
}
small {
  display: block;
}
.invitation-code {
  display: block;
  overflow-wrap: anywhere;
  user-select: all;
  padding: 10px;
  background: var(--fz-surface-soft);
}
.confirmation {
  display: flex;
  align-items: center;
  margin-block: 12px;
}
[role="alert"] {
  border-left: 3px solid var(--fz-accent);
  padding: 10px;
}
</style>

<style scoped>
.workspace-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  margin: 22px 0 8px;
  padding: 12px;
  border: 1px solid var(--fz-line);
  border-radius: 18px;
  background: var(--fz-surface-soft);
}
.workspace-selection {
  --selection-accent: var(--fz-accent);
  position: relative;
  min-width: 0;
  border: 1px solid var(--fz-line);
  border-radius: 11px;
  background: var(--fz-surface);
  overflow: hidden;
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease;
}
.workspace-selection::before {
  position: absolute;
  inset: 10px auto 10px 0;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--fz-accent);
  content: "";
}
.workspace-selection.is-shared {
  --selection-accent: var(--fz-workspace-shared-ink, #2458a6);
}
.workspace-selection.is-shared::before {
  background: var(--fz-workspace-shared-ink, #2458a6);
}
.workspace-selection-face {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 0;
  padding: 12px 14px;
}
.workspace-monogram {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border: 1px solid color-mix(in srgb, var(--fz-accent) 18%, var(--fz-line));
  border-radius: 10px;
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
  font-size: 19px;
  font-weight: 800;
  letter-spacing: -0.05em;
}
.is-shared .workspace-monogram {
  background: var(--fz-workspace-shared-bg, #eaf1ff);
  color: var(--fz-workspace-shared-ink, #2458a6);
  border-color: var(--fz-workspace-shared-border, #b8cdf0);
}
.workspace-selection-copy {
  display: grid;
  flex: 1;
  min-width: 0;
  gap: 2px;
}
.workspace-selection-caption {
  color: var(--fz-muted);
  font-size: 10px;
  font-weight: 650;
  line-height: 1.3;
}
.workspace-selection-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--fz-ink);
  font-size: 16px;
  font-weight: 750;
  line-height: 1.4;
  letter-spacing: -0.035em;
}
.workspace-switch-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  stroke: var(--fz-muted);
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.workspace-selection select {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}
.workspace-selection:hover:not(.is-disabled) {
  border-color: var(--selection-accent);
}
.workspace-selection:has(select:focus-visible) {
  outline: 3px solid var(--selection-accent);
  outline-offset: 3px;
}
.workspace-selection.is-disabled {
  opacity: 0.6;
}
.workspace-selection select:disabled {
  cursor: default;
}
.workspace-actions {
  display: flex;
  align-items: center;
  gap: 7px;
  padding-left: 16px;
  border-left: 1px solid var(--fz-line);
}
.workspace-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 40px;
  padding: 10px 12px;
  border-radius: 9px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.25;
  white-space: nowrap;
}
.workspace-actions svg {
  width: 16px;
  height: 16px;
  stroke: currentColor;
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-linejoin: round;
  flex-shrink: 0;
}
.workspace-actions .workspace-create {
  background: var(--fz-ink);
  color: var(--fz-surface);
  border-color: var(--fz-ink);
}
.workspace-actions .workspace-join {
  background: transparent;
  color: var(--fz-muted);
  border-color: transparent;
}
.workspace-actions button:hover:not(:disabled) {
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
}
.workspace-actions .workspace-join:hover:not(:disabled) {
  background: var(--fz-surface);
  color: var(--fz-ink);
  border-color: var(--fz-line);
}
.workspace-action-dialog button[type="submit"] {
  background: var(--fz-accent-soft);
  color: var(--fz-ink);
  border-color: var(--fz-accent);
}
@container (max-width: 590px) {
  .workspace-toolbar {
    grid-template-columns: minmax(0, 1fr);
    gap: 10px;
  }
  .workspace-actions {
    justify-content: flex-end;
    padding: 0;
    border: 0;
  }
}
@container (max-width: 340px) {
  .workspace-selection-face {
    gap: 8px;
    padding: 11px;
  }
  .workspace-monogram {
    width: 32px;
    height: 32px;
    font-size: 17px;
  }
  .workspace-selection-name {
    font-size: 14px;
  }
  .workspace-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .workspace-actions button {
    white-space: normal;
    text-align: left;
    padding: 9px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .workspace-selection {
    transition: none;
  }
}
.workspace-action-dialog {
  width: min(440px, calc(100vw - 32px));
  max-height: calc(100dvh - 32px);
  padding: 0;
  border: 1px solid var(--fz-line);
  border-radius: 20px;
  color: var(--fz-ink);
  background: var(--fz-surface);
  box-shadow: 0 32px 100px rgba(0, 0, 0, 0.3);
}
.workspace-action-dialog::backdrop {
  background: rgba(5, 10, 7, 0.5);
  backdrop-filter: blur(10px) saturate(0.85);
}
.workspace-dialog-body {
  padding: 24px;
}
.workspace-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.workspace-dialog-header h3 {
  font-size: 20px;
}
.workspace-dialog-header button {
  width: 34px;
  height: 34px;
  padding: 0;
  font-size: 22px;
  flex-shrink: 0;
}
.workspace-action-dialog form {
  display: grid;
  gap: 16px;
  margin: 18px 0 0;
}
.workspace-action-dialog input {
  width: 100%;
}
.workspace-action-dialog footer {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}
.workspace-action-dialog p {
  color: var(--fz-muted);
}
.workspace-action-dialog [role="alert"] {
  color: var(--fz-ink);
  margin: 0;
}
</style>
