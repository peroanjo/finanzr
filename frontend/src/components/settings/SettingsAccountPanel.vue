<script setup lang="ts">
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{
  initialDisplayName: string;
  initialEmail: string;
  roleLabel: string;
  identityBusy: boolean;
  identityError: string;
  identitySuccess: string;
  passwordBusy: boolean;
  passwordError: string;
  passwordSuccess: string;
}>();

const emit = defineEmits<{
  saveIdentity: [payload: { displayName: string; email: string; password: string }];
  savePassword: [
    payload: {
      currentPassword: string;
      newPassword: string;
      confirmation: string;
    },
  ];
}>();

const { t } = useI18n();
const accountDisplayName = ref(props.initialDisplayName);
const accountEmail = ref(props.initialEmail);
const identityPassword = ref("");
const currentPassword = ref("");
const newPassword = ref("");
const passwordConfirmation = ref("");

watch(
  () => props.initialDisplayName,
  (value) => {
    accountDisplayName.value = value;
  },
);
watch(
  () => props.initialEmail,
  (value) => {
    accountEmail.value = value;
  },
);
watch(
  () => props.identitySuccess,
  (success) => {
    if (success) identityPassword.value = "";
  },
);
watch(
  () => props.passwordSuccess,
  (success) => {
    if (success) {
      currentPassword.value = "";
      newPassword.value = "";
      passwordConfirmation.value = "";
    }
  },
);

function saveIdentity() {
  emit("saveIdentity", {
    displayName: accountDisplayName.value,
    email: accountEmail.value,
    password: identityPassword.value,
  });
}

function savePassword() {
  emit("savePassword", {
    currentPassword: currentPassword.value,
    newPassword: newPassword.value,
    confirmation: passwordConfirmation.value,
  });
}
</script>

<template>
  <article class="account-document">
    <header class="account-document-header">
      <div>
        <p>{{ t("settings.identityAndAccess") }}</p>
        <h3>{{ t("settings.yourAccount") }}</h3>
      </div>
      <span>{{ props.roleLabel }}</span>
    </header>
    <p class="account-intro">{{ t("settings.accountIntro") }}</p>

    <div class="account-form-grid">
      <form class="account-form-card" @submit.prevent="saveIdentity">
        <header>
          <span aria-hidden="true">@</span>
          <div>
            <p>{{ t("settings.identification") }}</p>
            <h4>{{ t("settings.profileAndEmail") }}</h4>
          </div>
        </header>
        <p>{{ t("settings.identityHelp") }}</p>
        <label>
          <span>{{ t("settings.displayName") }}</span>
          <input
            v-model.trim="accountDisplayName"
            type="text"
            autocomplete="name"
            maxlength="120"
          />
        </label>
        <label>
          <span>{{ t("settings.email") }}</span>
          <input
            v-model.trim="accountEmail"
            type="email"
            autocomplete="email"
            required
          />
        </label>
        <label>
          <span>{{ t("settings.currentPassword") }}</span>
          <input
            v-model="identityPassword"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <p v-if="props.identityError" class="account-form-message error" role="alert">
          {{ props.identityError }}
        </p>
        <p v-else-if="props.identitySuccess" class="account-form-message success" role="status">
          {{ props.identitySuccess }}
        </p>
        <button type="submit" :disabled="props.identityBusy">
          {{ props.identityBusy ? t("common.saving") : t("settings.saveProfile") }}
        </button>
      </form>

      <form class="account-form-card" @submit.prevent="savePassword">
        <header>
          <span aria-hidden="true">••</span>
          <div>
            <p>{{ t("settings.security") }}</p>
            <h4>{{ t("settings.password") }}</h4>
          </div>
        </header>
        <p>{{ t("settings.passwordHelp") }}</p>
        <label>
          <span>{{ t("settings.currentPassword") }}</span>
          <input
            v-model="currentPassword"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <label>
          <span>{{ t("settings.newPassword") }}</span>
          <input
            v-model="newPassword"
            type="password"
            autocomplete="new-password"
            minlength="12"
            required
          />
        </label>
        <label>
          <span>{{ t("settings.repeatNewPassword") }}</span>
          <input
            v-model="passwordConfirmation"
            type="password"
            autocomplete="new-password"
            minlength="12"
            required
          />
        </label>
        <p v-if="props.passwordError" class="account-form-message error" role="alert">
          {{ props.passwordError }}
        </p>
        <p v-else-if="props.passwordSuccess" class="account-form-message success" role="status">
          {{ props.passwordSuccess }}
        </p>
        <button type="submit" :disabled="props.passwordBusy">
          {{ props.passwordBusy ? t("settings.updating") : t("settings.changePassword") }}
        </button>
      </form>
    </div>
  </article>
</template>

<style scoped>
.account-document { padding: 34px 38px 48px; }
.account-document-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
.account-document-header p { margin: 0 0 6px; color: var(--fz-muted); font-size: 10px; font-weight: 760; letter-spacing: 0.1em; text-transform: uppercase; }
.account-document-header h3 { margin: 0; font-size: 29px; letter-spacing: -0.045em; }
.account-document-header > span { padding: 6px 9px; border: 1px solid color-mix(in srgb, var(--fz-accent) 24%, var(--fz-line)); border-radius: 99px; background: var(--fz-accent-soft); color: var(--fz-accent); font-size: 10px; font-weight: 780; }
.account-intro { max-width: 650px; margin: 12px 0 0; color: var(--fz-muted); font-size: 12px; line-height: 1.6; }
.account-form-grid { margin-top: 27px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-items: start; }
.account-form-card { min-width: 0; padding: 19px; display: grid; gap: 13px; border: 1px solid var(--fz-line); border-radius: 16px; background: var(--fz-surface-soft); }
.account-form-card > header { display: flex; align-items: center; gap: 10px; padding-bottom: 13px; border-bottom: 1px solid var(--fz-line); }
.account-form-card > header > span { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 10px; background: var(--fz-accent-soft); color: var(--fz-accent); font-size: 10px; font-weight: 820; }
.account-form-card > header div { display: grid; gap: 2px; }
.account-form-card > header p { margin: 0; color: var(--fz-accent); font-size: 10px; font-weight: 780; letter-spacing: 0.1em; text-transform: uppercase; }
.account-form-card h4 { margin: 0; font-size: 15px; letter-spacing: -0.025em; }
.account-form-card > p { min-height: 29px; margin: 0; color: var(--fz-muted); font-size: 11px; line-height: 1.55; }
.account-form-card label { display: grid; gap: 6px; }
.account-form-card label > span { color: var(--fz-muted); font-size: 11px; font-weight: 700; }
.account-form-card input { width: 100%; height: 43px; padding: 0 11px; border: 1px solid var(--fz-line); border-radius: 10px; outline: 0; background: var(--fz-surface); color: var(--fz-ink); font: 600 12px inherit; transition: border-color 0.16s ease, box-shadow 0.16s ease; }
.account-form-card input:focus { border-color: color-mix(in srgb, var(--fz-accent) 58%, var(--fz-line)); box-shadow: 0 0 0 3px color-mix(in srgb, var(--fz-accent) 10%, transparent); }
.account-form-card > button { justify-self: start; min-width: 130px; margin-top: 2px; padding: 10px 13px; border: 0; border-radius: 10px; background: var(--fz-accent); color: #092418; font-size: 11px; font-weight: 780; cursor: pointer; }
.account-form-card > button:disabled { opacity: 0.55; cursor: wait; }
.account-form-message { min-height: 0 !important; margin: 0; padding: 8px 10px; border-radius: 8px; font-size: 11px; font-weight: 680; }
.account-form-message.error { background: color-mix(in srgb, var(--fz-negative) 9%, transparent); color: var(--fz-negative); }
.account-form-message.success { background: var(--fz-accent-soft); color: var(--fz-accent); }
@media (max-width: 1060px) { .account-form-grid { grid-template-columns: 1fr; } .account-document { padding-inline: 28px; } }
@media (max-width: 720px) { .account-document { padding: 22px 17px 34px; } .account-document-header h3 { font-size: 24px; } .account-form-grid { margin-top: 20px; } .account-form-card { padding: 16px; } }
</style>
