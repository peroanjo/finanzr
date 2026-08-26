<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { api, json } from "../../api/client";
import type { AdminUser } from "../../types/api";
import { useLocalePreference } from "../../i18n";

const { t } = useI18n();
const { locale } = useLocalePreference();

const users = ref<AdminUser[]>([]);
const loading = ref(true);
const error = ref("");
const notice = ref("");
const editorMode = ref<"create" | "edit" | null>(null);
const editingUser = ref<AdminUser | null>(null);
const saving = ref(false);
const busyUserId = ref("");
const pendingDelete = ref<AdminUser | null>(null);
const form = ref({
  display_name: "",
  email: "",
  role: "user" as AdminUser["role"],
  password: "",
  password_confirmation: "",
});
const activeCount = computed(
  () => users.value.filter((user) => user.is_active).length,
);

function initials(user: AdminUser) {
  const source = user.display_name || user.email;
  return source
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function roleLabel(role: AdminUser["role"]) {
  return role === "admin"
    ? t("adminUsers.roleAdminShort")
    : role === "demo"
      ? t("adminUsers.roleDemo")
      : t("adminUsers.roleUser");
}

function joinedLabel(value: string) {
  return new Intl.DateTimeFormat(locale.value, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    users.value = await api<AdminUser[]>("/administration/users");
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : t("adminUsers.loadError");
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  error.value = "";
  notice.value = "";
  editingUser.value = null;
  form.value = {
    display_name: "",
    email: "",
    role: "user",
    password: "",
    password_confirmation: "",
  };
  editorMode.value = "create";
}

function openEdit(user: AdminUser) {
  error.value = "";
  notice.value = "";
  editingUser.value = user;
  form.value = {
    display_name: user.display_name,
    email: user.email,
    role: user.role,
    password: "",
    password_confirmation: "",
  };
  editorMode.value = "edit";
}

function closeEditor() {
  editorMode.value = null;
  editingUser.value = null;
}

async function saveUser() {
  error.value = "";
  notice.value = "";
  if (form.value.password !== form.value.password_confirmation) {
    error.value = t("adminUsers.passwordMismatch");
    return;
  }
  saving.value = true;
  try {
    if (editorMode.value === "edit" && editingUser.value) {
      const body: Record<string, string> = {
        display_name: form.value.display_name,
        email: form.value.email,
        role: form.value.role,
      };
      if (form.value.password) {
        body.password = form.value.password;
        body.password_confirmation = form.value.password_confirmation;
      }
      const updated = await api<AdminUser>(
        `/administration/users/${editingUser.value.id}`,
        json("PATCH", body),
      );
      users.value = users.value.map((user) =>
        user.id === updated.id ? updated : user,
      );
      notice.value = t("adminUsers.accountUpdated", { email: updated.email });
    } else {
      const created = await api<AdminUser>(
        "/administration/users",
        json("POST", form.value),
      );
      users.value.push(created);
      users.value.sort((left, right) =>
        left.date_joined.localeCompare(right.date_joined),
      );
      notice.value = t("adminUsers.accountCreated", { email: created.email });
    }
    closeEditor();
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : t("adminUsers.saveError");
  } finally {
    saving.value = false;
  }
}

async function toggleAccess(user: AdminUser) {
  error.value = "";
  notice.value = "";
  busyUserId.value = user.id;
  try {
    const updated = await api<AdminUser>(
      `/administration/users/${user.id}`,
      json("PATCH", { is_active: !user.is_active }),
    );
    users.value = users.value.map((item) =>
      item.id === updated.id ? updated : item,
    );
    notice.value = updated.is_active
      ? t("adminUsers.accessRestored", { email: updated.email })
      : t("adminUsers.accessBlocked", { email: updated.email });
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t("adminUsers.accessChangeError");
  } finally {
    busyUserId.value = "";
  }
}

async function deleteUser() {
  if (!pendingDelete.value) return;
  const target = pendingDelete.value;
  error.value = "";
  notice.value = "";
  busyUserId.value = target.id;
  try {
    await api(`/administration/users/${target.id}`, { method: "DELETE" });
    users.value = users.value.filter((user) => user.id !== target.id);
    pendingDelete.value = null;
    notice.value = t("adminUsers.accessDeleted", { email: target.email });
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : t("adminUsers.deleteError");
    pendingDelete.value = null;
  } finally {
    busyUserId.value = "";
  }
}

onMounted(load);
</script>

<template>
  <article class="admin-users-panel">
    <header class="admin-users-header">
      <div>
        <p>{{ t("adminUsers.accessAdministration") }}</p>
        <h3>{{ t("adminUsers.title") }}</h3>
        <span
          >{{ t("adminUsers.registeredUsers", { count: users.length }) }} ·
          {{ t("adminUsers.activeUsers", { count: activeCount }) }}</span
        >
      </div>
      <button type="button" @click="openCreate">
        {{ t("adminUsers.createAccount") }}
      </button>
    </header>

    <form
      v-if="editorMode"
      class="admin-create-form"
      @submit.prevent="saveUser"
    >
      <header>
        <div>
          <p>
            {{
              editorMode === "create"
                ? t("adminUsers.newCredential")
                : t("adminUsers.editAccess")
            }}
          </p>
          <h4>
            {{
              editorMode === "create"
                ? t("adminUsers.createManually")
                : t("adminUsers.editUser", { email: editingUser?.email })
            }}
          </h4>
        </div>
        <button
          type="button"
          :aria-label="t('adminUsers.closeFormAria')"
          @click="closeEditor"
        >
          ×
        </button>
      </header>
      <div class="admin-create-grid">
        <label
          ><span>{{ t("adminUsers.displayName") }}</span
          ><input v-model.trim="form.display_name" autocomplete="name"
        /></label>
        <label
          ><span>{{ t("adminUsers.email") }}</span
          ><input
            v-model.trim="form.email"
            type="email"
            autocomplete="email"
            required
        /></label>
        <label>
          <span>{{ t("adminUsers.accountType") }}</span>
          <select v-model="form.role">
            <option value="user">{{ t("adminUsers.roleUser") }}</option>
            <option value="admin">{{ t("adminUsers.roleAdmin") }}</option>
            <option v-if="editorMode === 'edit'" value="demo">
              {{ t("adminUsers.roleDemo") }}
            </option>
          </select>
        </label>
        <label>
          <span>{{
            editorMode === "create"
              ? t("adminUsers.temporaryPassword")
              : t("adminUsers.newPasswordOptional")
          }}</span>
          <input
            v-model="form.password"
            type="password"
            autocomplete="new-password"
            minlength="12"
            :required="editorMode === 'create'"
          />
        </label>
        <label>
          <span>{{
            editorMode === "create"
              ? t("adminUsers.repeatPassword")
              : t("adminUsers.repeatNewPassword")
          }}</span>
          <input
            v-model="form.password_confirmation"
            type="password"
            autocomplete="new-password"
            minlength="12"
            :required="editorMode === 'create' || Boolean(form.password)"
          />
        </label>
      </div>
      <footer>
        <p>
          {{
            editorMode === "create"
              ? t("adminUsers.createHelp")
              : t("adminUsers.editHelp")
          }}
        </p>
        <button type="submit" :disabled="saving">
          {{
            saving
              ? t("common.saving")
              : editorMode === "create"
                ? t("adminUsers.createAccount").replace("+ ", "")
                : t("adminUsers.saveChanges")
          }}
        </button>
      </footer>
    </form>

    <p v-if="error" class="admin-users-message error" role="alert">
      {{ error }}
    </p>
    <p v-else-if="notice" class="admin-users-message success" role="status">
      {{ notice }}
    </p>

    <div
      v-if="loading"
      class="admin-users-loading"
      :aria-label="t('adminUsers.loadingAria')"
    >
      <i /><i /><i />
    </div>
    <div v-else class="admin-users-list">
      <div class="admin-users-list-head">
        <span>{{ t("adminUsers.columnUser") }}</span
        ><span>{{ t("adminUsers.columnRole") }}</span
        ><span>{{ t("adminUsers.columnStatus") }}</span
        ><span>{{ t("adminUsers.columnActions") }}</span>
      </div>
      <article
        v-for="user in users"
        :key="user.id"
        :class="{ blocked: !user.is_active }"
      >
        <div class="admin-user-identity">
          <span>{{ initials(user) }}</span>
          <p>
            <strong>{{ user.display_name || t("adminUsers.unnamed") }}</strong
            ><small
              >{{ user.email }} ·
              {{
                t("adminUsers.joined", { date: joinedLabel(user.date_joined) })
              }}</small
            >
          </p>
        </div>
        <div>
          <span class="admin-role" :class="user.role">{{
            roleLabel(user.role)
          }}</span>
        </div>
        <div>
          <span class="admin-status" :class="{ active: user.is_active }"
            ><i />{{
              user.is_active ? t("adminUsers.active") : t("adminUsers.blocked")
            }}</span
          >
        </div>
        <div v-if="user.is_self" class="admin-self-label">
          {{ t("adminUsers.yourAccount") }}
        </div>
        <div v-else class="admin-user-actions">
          <button
            class="edit"
            type="button"
            :disabled="busyUserId === user.id"
            @click="openEdit(user)"
          >
            {{ t("adminUsers.edit") }}
          </button>
          <button
            type="button"
            :disabled="busyUserId === user.id"
            @click="toggleAccess(user)"
          >
            {{
              user.is_active ? t("adminUsers.block") : t("adminUsers.restore")
            }}
          </button>
          <button
            class="delete"
            type="button"
            :disabled="busyUserId === user.id"
            @click="pendingDelete = user"
          >
            {{ t("adminUsers.delete") }}
          </button>
        </div>
      </article>
    </div>

    <div
      v-if="pendingDelete"
      class="admin-delete-confirm"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="delete-user-title"
    >
      <div>
        <p>{{ t("adminUsers.deleteAccess") }}</p>
        <h4 id="delete-user-title">
          {{ t("adminUsers.deleteQuestion", { email: pendingDelete.email }) }}
        </h4>
        <span>{{ t("adminUsers.deleteWarning") }}</span>
        <footer>
          <button type="button" @click="pendingDelete = null">
            {{ t("common.cancel") }}</button
          ><button class="danger" type="button" @click="deleteUser">
            {{ t("adminUsers.deleteAccount") }}
          </button>
        </footer>
      </div>
    </div>
  </article>
</template>

<style scoped>
.admin-users-panel {
  position: relative;
  padding: 32px 36px 46px;
}
.admin-users-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}
.admin-users-header p,
.admin-create-form header p {
  margin: 0 0 5px;
  color: var(--fz-accent);
  font-size: 7px;
  font-weight: 780;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.admin-users-header h3 {
  margin: 0;
  font-size: 27px;
  letter-spacing: -0.045em;
}
.admin-users-header > div > span {
  display: block;
  margin-top: 7px;
  color: var(--fz-muted);
  font-size: 8px;
}
.admin-users-header > button {
  padding: 10px 13px;
  border: 0;
  border-radius: 10px;
  background: var(--fz-accent);
  color: #092418;
  font-size: 8px;
  font-weight: 790;
  cursor: pointer;
}
.admin-create-form {
  margin-top: 20px;
  padding: 17px;
  border: 1px solid color-mix(in srgb, var(--fz-accent) 24%, var(--fz-line));
  border-radius: 16px;
  background: color-mix(in srgb, var(--fz-accent) 4%, var(--fz-surface-soft));
  box-shadow: 0 14px 36px rgba(21, 44, 31, 0.06);
}
.admin-create-form > header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
.admin-create-form h4 {
  margin: 0;
  font-size: 13px;
}
.admin-create-form > header > button {
  border: 0;
  background: transparent;
  color: var(--fz-muted);
  font-size: 18px;
  cursor: pointer;
}
.admin-create-grid {
  margin-top: 15px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 11px;
}
.admin-create-grid label {
  display: grid;
  gap: 6px;
}
.admin-create-grid label > span {
  color: var(--fz-muted);
  font-size: 7px;
  font-weight: 700;
}
.admin-create-grid input,
.admin-create-grid select {
  width: 100%;
  height: 38px;
  padding: 0 10px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  outline: 0;
  background: var(--fz-surface);
  color: var(--fz-ink);
  font-family: inherit;
  font-size: 8px;
}
.admin-create-grid input:focus,
.admin-create-grid select:focus {
  border-color: var(--fz-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 10%, transparent);
}
.admin-create-form > footer {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.admin-create-form > footer p {
  margin: 0;
  color: var(--fz-muted);
  font-size: 7px;
}
.admin-create-form > footer button {
  padding: 9px 12px;
  border: 0;
  border-radius: 9px;
  background: var(--fz-accent);
  color: #092418;
  font-size: 8px;
  font-weight: 780;
}
.admin-users-message {
  margin: 17px 0 0;
  padding: 10px 12px;
  border-radius: 9px;
  font-size: 8px;
  font-weight: 680;
}
.admin-users-message.error {
  background: color-mix(in srgb, var(--fz-negative) 9%, transparent);
  color: var(--fz-negative);
}
.admin-users-message.success {
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
}
.admin-users-loading {
  margin-top: 24px;
  display: grid;
  gap: 7px;
}
.admin-users-loading i {
  height: 62px;
  border-radius: 12px;
  background: var(--fz-surface-soft);
}
.admin-users-list {
  margin-top: 24px;
  border-top: 1px solid var(--fz-line);
}
.admin-users-list-head,
.admin-users-list > article {
  display: grid;
  grid-template-columns: minmax(220px, 1.5fr) 85px 90px minmax(145px, 0.8fr);
  gap: 12px;
  align-items: center;
}
.admin-users-list-head {
  padding: 8px 12px;
  color: var(--fz-muted);
  font-size: 6px;
  font-weight: 760;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.admin-users-list > article {
  min-height: 65px;
  padding: 10px 12px;
  border-top: 1px solid var(--fz-line);
  transition:
    opacity 0.16s ease,
    background 0.16s ease;
}
.admin-users-list > article:hover {
  background: var(--fz-surface-soft);
}
.admin-users-list > article.blocked {
  opacity: 0.62;
}
.admin-user-identity {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}
.admin-user-identity > span {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
  font-size: 8px;
  font-weight: 820;
}
.admin-user-identity p {
  min-width: 0;
  margin: 0;
  display: grid;
  gap: 3px;
}
.admin-user-identity strong,
.admin-user-identity small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.admin-user-identity strong {
  font-size: 9px;
}
.admin-user-identity small {
  color: var(--fz-muted);
  font-size: 7px;
}
.admin-role,
.admin-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 7px;
  border-radius: 99px;
  font-size: 7px;
  font-weight: 730;
}
.admin-role {
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
}
.admin-role.admin {
  background: var(--fz-accent-soft);
  color: var(--fz-accent);
}
.admin-role.demo {
  background: color-mix(in srgb, #8b7cf6 10%, transparent);
  color: #8172e8;
}
.admin-status {
  color: var(--fz-muted);
}
.admin-status i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.admin-status.active {
  color: var(--fz-accent);
}
.admin-user-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}
.admin-user-actions button {
  padding: 7px 8px;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  font-size: 7px;
  cursor: pointer;
}
.admin-user-actions button:hover {
  color: var(--fz-ink);
  background: var(--fz-surface);
}
.admin-user-actions button.delete:hover {
  border-color: color-mix(in srgb, var(--fz-negative) 35%, var(--fz-line));
  color: var(--fz-negative);
}
.admin-user-actions button:disabled {
  opacity: 0.45;
  cursor: wait;
}
.admin-self-label {
  text-align: right;
  color: var(--fz-accent);
  font-size: 7px;
  font-weight: 720;
}
.admin-delete-confirm {
  position: absolute;
  z-index: 3;
  inset: 0;
  padding: 24px;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--fz-surface) 70%, transparent);
  backdrop-filter: blur(7px);
}
.admin-delete-confirm > div {
  width: min(390px, 100%);
  padding: 22px;
  border: 1px solid var(--fz-line);
  border-radius: 17px;
  background: var(--fz-surface);
  box-shadow: 0 22px 60px rgba(3, 10, 6, 0.22);
}
.admin-delete-confirm p {
  margin: 0 0 6px;
  color: var(--fz-negative);
  font-size: 7px;
  font-weight: 780;
  text-transform: uppercase;
}
.admin-delete-confirm h4 {
  margin: 0;
  font-size: 15px;
  line-height: 1.35;
}
.admin-delete-confirm > div > span {
  display: block;
  margin-top: 10px;
  color: var(--fz-muted);
  font-size: 8px;
  line-height: 1.55;
}
.admin-delete-confirm footer {
  margin-top: 18px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.admin-delete-confirm button {
  padding: 9px 11px;
  border: 1px solid var(--fz-line);
  border-radius: 9px;
  background: transparent;
  color: var(--fz-ink);
  font-size: 8px;
}
.admin-delete-confirm button.danger {
  border-color: transparent;
  background: var(--fz-negative);
  color: white;
}
@media (max-width: 1050px) {
  .admin-users-list-head {
    display: none;
  }
  .admin-users-list > article {
    grid-template-columns: minmax(180px, 1fr) auto auto;
    grid-template-areas: "identity role status" "identity actions actions";
  }
  .admin-user-identity {
    grid-area: identity;
  }
  .admin-user-actions,
  .admin-self-label {
    grid-area: actions;
  }
  .admin-role {
    grid-area: role;
  }
  .admin-status {
    grid-area: status;
  }
  .admin-create-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 720px) {
  .admin-users-panel {
    padding: 22px 17px 34px;
  }
  .admin-users-header h3 {
    font-size: 22px;
  }
  .admin-users-header {
    align-items: center;
  }
  .admin-users-list > article {
    grid-template-columns: 1fr auto;
    grid-template-areas: "identity status" "role actions";
    gap: 8px;
  }
  .admin-user-actions {
    justify-content: flex-end;
  }
  .admin-create-form > footer {
    align-items: flex-end;
  }
}
@media (min-width: 1051px) {
  .admin-users-list-head,
  .admin-users-list > article {
    grid-template-columns: minmax(220px, 1.5fr) 85px 90px minmax(190px, 0.9fr);
  }
}
.admin-user-actions button.edit:hover {
  border-color: color-mix(in srgb, var(--fz-accent) 35%, var(--fz-line));
  color: var(--fz-accent);
}

/* Administration uses the same readable scale as Account and Importers. */
.admin-users-header p,
.admin-create-form header p,
.admin-create-grid label > span,
.admin-create-form > footer p,
.admin-users-list-head,
.admin-user-identity > span,
.admin-user-identity small,
.admin-role,
.admin-status,
.admin-self-label,
.admin-delete-confirm p {
  font-size: 10px;
}
.admin-users-header > div > span,
.admin-users-header > button,
.admin-create-grid input,
.admin-create-grid select,
.admin-create-form > footer button,
.admin-users-message,
.admin-user-identity strong,
.admin-user-actions button,
.admin-delete-confirm > div > span,
.admin-delete-confirm button {
  font-size: 11px;
}
.admin-create-form h4 {
  font-size: 15px;
}
.admin-create-grid input,
.admin-create-grid select {
  height: 42px;
  font-size: 12px;
}
.admin-users-list > article {
  min-height: 72px;
}
.admin-user-identity > span {
  width: 38px;
  height: 38px;
}
.admin-delete-confirm h4 {
  font-size: 17px;
}
</style>
