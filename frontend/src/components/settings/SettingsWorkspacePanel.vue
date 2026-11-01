<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
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
const newName = ref("");
const email = ref("");
const inviteRole = ref("editor");
const invitationCode = ref("");
const acceptCode = ref("");
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
function create() {
  return run(() =>
    apply(
      api<UserSession>("/workspaces", json("POST", { name: newName.value })),
    ),
  );
}
function rename() {
  return run(() =>
    api("/workspaces/settings", json("PATCH", { name: name.value })).then(() =>
      session.restore(),
    ),
  );
}
function accept() {
  return run(() =>
    apply(
      api<UserSession>(
        "/workspaces/invitations/accept",
        json("POST", { token: acceptCode.value.trim() }),
      ),
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
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="busy" role="status">{{ t("workspace.loading") }}</p>
    <section v-if="settings">
      <h4>
        {{ settings.name }}
        <small>{{
          t(settings.is_personal ? "workspace.personal" : "workspace.shared")
        }}</small>
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
    <section>
      <h4>{{ t("workspace.create") }}</h4>
      <p>{{ t("workspace.createHelp") }}</p>
      <form @submit.prevent="create">
        <label
          >{{ t("workspace.name")
          }}<input v-model="newName" required maxlength="120" /></label
        ><button :disabled="busy">{{ t("workspace.create") }}</button>
      </form>
      <form @submit.prevent="accept">
        <label
          >{{ t("workspace.invitationCode")
          }}<input v-model="acceptCode" required autocomplete="off" /></label
        ><button :disabled="busy">{{ t("workspace.accept") }}</button>
      </form>
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
  </article>
</template>

<style scoped>
.workspace-panel {
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
