<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useSessionStore } from "../stores/session";
import { buildLabel } from "../buildInfo";
import { useLocalePreference } from "../i18n";

const email = ref("");
const password = ref("");
const error = ref("");
const submitting = ref(false);
const passwordVisible = ref(false);
const session = useSessionStore();
const router = useRouter();
const { t } = useI18n();
const {
  locale,
  supportedLocales,
  selectLoginLocale,
  hasLoginLocaleChoice,
  clearLoginLocaleChoice,
  loadInstallationLocale,
} = useLocalePreference();

onMounted(loadInstallationLocale);

async function submit() {
  if (submitting.value) return;
  error.value = "";
  submitting.value = true;
  try {
    const requestedLocale = locale.value;
    const persistRequestedLocale = hasLoginLocaleChoice();
    await session.login(email.value, password.value);
    if (persistRequestedLocale) {
      await session.updateLanguage(requestedLocale);
      clearLoginLocaleChoice();
    }
    await router.push("/");
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : t("login.genericError");
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="login-landing">
    <div class="ambient" aria-hidden="true">
      <span class="ambient-orbit orbit-one" />
      <span class="ambient-orbit orbit-two" />
      <span class="ambient-glow" />
      <svg
        class="ambient-signal"
        viewBox="0 0 1200 620"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="signal-gradient" x1="0" x2="1">
            <stop offset="0" stop-color="#6ee7ae" stop-opacity="0" />
            <stop offset=".25" stop-color="#6ee7ae" stop-opacity=".6" />
            <stop offset=".72" stop-color="#718fdb" stop-opacity=".45" />
            <stop offset="1" stop-color="#718fdb" stop-opacity="0" />
          </linearGradient>
        </defs>
        <path
          class="signal-shadow"
          d="M-30 460 C110 440 150 485 280 420 S460 335 570 370 S710 270 830 300 S990 170 1230 210"
        />
        <path
          class="signal-line"
          d="M-30 460 C110 440 150 485 280 420 S460 335 570 370 S710 270 830 300 S990 170 1230 210"
        />
        <circle cx="280" cy="420" r="4" />
        <circle cx="570" cy="370" r="4" />
        <circle cx="830" cy="300" r="4" />
      </svg>
    </div>

    <header class="landing-header">
      <a class="landing-brand" href="/app/login" aria-label="Finanzr">
        <span>finanzr<span aria-hidden="true">.</span></span>
      </a>
      <div class="landing-actions">
        <label class="login-language-picker">
          <span>{{ t("login.selectLanguage") }}</span>
          <select
            :value="locale"
            :aria-label="t('login.selectLanguage')"
            @change="
              selectLoginLocale(
                ($event.target as HTMLSelectElement).value as 'es-ES' | 'en',
              )
            "
          >
            <option
              v-for="item in supportedLocales"
              :key="item.code"
              :value="item.code"
            >
              {{ item.label }}
            </option>
          </select>
        </label>
        <div class="private-installation">
          <i /> {{ t("login.privateInstallation") }}
        </div>
      </div>
    </header>

    <section class="landing-content">
      <div class="landing-story">
        <div class="story-copy">
          <p class="story-kicker"><span>01</span> {{ t("login.kicker") }}</p>
          <h1>
            {{ t("login.titleFirst") }}<br /><em>{{
              t("login.titleSecond")
            }}</em>
          </h1>
          <p class="story-intro">{{ t("login.intro") }}</p>
        </div>

        <div
          class="product-window"
          :aria-label="t('login.dashboardPreviewAria')"
        >
          <header>
            <div>
              <span class="window-dot" /><span class="window-dot" /><span
                class="window-dot"
              />
            </div>
            <small>{{ t("login.consolidatedView") }}</small>
            <span class="window-live"><i /> {{ t("login.updated") }}</span>
          </header>
          <div class="window-body">
            <div class="window-total">
              <small>{{ t("login.netWorth") }}</small>
              <strong>{{ t("login.underControl") }}</strong>
              <span>{{ t("login.clearReading") }}</span>
            </div>
            <div class="window-chart" aria-hidden="true">
              <svg viewBox="0 0 420 120" preserveAspectRatio="none">
                <defs>
                  <linearGradient
                    id="area-gradient"
                    x1="0"
                    x2="0"
                    y1="0"
                    y2="1"
                  >
                    <stop offset="0" stop-color="#6ee7ae" stop-opacity=".32" />
                    <stop offset="1" stop-color="#6ee7ae" stop-opacity="0" />
                  </linearGradient>
                </defs>
                <path
                  class="chart-area"
                  d="M0 102 C40 94 56 103 88 84 S137 76 167 69 S220 80 249 54 S302 61 330 36 S377 30 420 11 L420 120 L0 120 Z"
                />
                <path
                  class="chart-stroke"
                  d="M0 102 C40 94 56 103 88 84 S137 76 167 69 S220 80 249 54 S302 61 330 36 S377 30 420 11"
                />
              </svg>
            </div>
            <div class="asset-ribbon">
              <span><i class="mint" /> {{ t("login.savings") }}</span>
              <span><i class="blue" /> {{ t("login.investment") }}</span>
              <span><i class="violet" /> {{ t("login.realEstate") }}</span>
              <span><i class="gold" /> {{ t("navigation.crypto") }}</span>
            </div>
          </div>
        </div>

        <ul class="trust-list" :aria-label="t('login.principlesAria')">
          <li>
            <span>{{ t("login.selfHosted") }}</span
            ><small>{{ t("login.selfHostedCopy") }}</small>
          </li>
          <li>
            <span>{{ t("login.privateByDesign") }}</span
            ><small>{{ t("login.privateByDesignCopy") }}</small>
          </li>
          <li>
            <span>{{ t("login.completeView") }}</span
            ><small>{{ t("login.completeViewCopy") }}</small>
          </li>
        </ul>
      </div>

      <aside class="login-panel">
        <form @submit.prevent="submit">
          <header>
            <p>{{ t("login.secureAccess") }}</p>
            <h2>{{ t("login.enterSpace") }}</h2>
            <span>{{ t("login.credentialsHint") }}</span>
          </header>

          <div class="form-fields">
            <label>
              <span>{{ t("login.email") }}</span>
              <div class="input-shell">
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <path d="M3.5 5.5h13v9h-13zM4 6l6 4 6-4" />
                </svg>
                <input
                  v-model.trim="email"
                  autocomplete="email"
                  inputmode="email"
                  type="email"
                  :placeholder="t('login.emailPlaceholder')"
                  required
                />
              </div>
            </label>
            <label>
              <span>{{ t("login.password") }}</span>
              <div class="input-shell">
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <rect x="4" y="8" width="12" height="9" rx="2" />
                  <path d="M7 8V6a3 3 0 0 1 6 0v2" />
                </svg>
                <input
                  v-model="password"
                  autocomplete="current-password"
                  :type="passwordVisible ? 'text' : 'password'"
                  :placeholder="t('login.passwordPlaceholder')"
                  required
                />
                <button
                  class="password-toggle"
                  type="button"
                  :aria-label="
                    passwordVisible
                      ? t('login.hidePassword')
                      : t('login.showPassword')
                  "
                  @click="passwordVisible = !passwordVisible"
                >
                  {{ passwordVisible ? t("login.hide") : t("login.show") }}
                </button>
              </div>
            </label>
          </div>

          <div v-if="error" class="login-error" role="alert">
            <span aria-hidden="true">!</span>
            <p>{{ error }}</p>
          </div>

          <button class="login-submit" type="submit" :disabled="submitting">
            <span>{{
              submitting ? t("login.checking") : t("login.submit")
            }}</span>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M4 10h11M11 6l4 4-4 4" />
            </svg>
          </button>

          <footer>
            <span class="security-mark"
              ><svg viewBox="0 0 20 20" aria-hidden="true">
                <path
                  d="M10 2.5l6 2v4.8c0 3.8-2.5 6.5-6 8.2-3.5-1.7-6-4.4-6-8.2V4.5zM7.5 10l1.7 1.7 3.5-3.7"
                /></svg
            ></span>
            <p>
              <strong>{{ t("login.protectedConnection") }}</strong
              ><small>{{ t("login.sessionOnServer") }}</small>
            </p>
          </footer>
        </form>
      </aside>
    </section>

    <footer class="landing-footer">
      <span>{{ t("login.footer") }}</span>
      <span>{{ t("login.version", { version: buildLabel }) }}</span>
    </footer>
  </main>
</template>

<style scoped>
.login-landing {
  --login-bg: #09110e;
  --login-surface: rgba(18, 29, 24, 0.82);
  --login-line: rgba(194, 225, 209, 0.13);
  --login-ink: #f2f7f4;
  --login-muted: #8fa299;
  --login-mint: #6ee7ae;
  --login-blue: #718fdb;
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  padding: 30px clamp(28px, 4.5vw, 72px) 22px;
  background: var(--login-bg);
  color: var(--login-ink);
  isolation: isolate;
}
.login-landing::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -3;
  background:
    linear-gradient(rgba(255, 255, 255, 0.018) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.018) 1px, transparent 1px);
  background-size: 72px 72px;
  mask-image: linear-gradient(to bottom, black, transparent 86%);
}
.ambient {
  position: absolute;
  inset: 0;
  z-index: -2;
  overflow: hidden;
  pointer-events: none;
}
.ambient-glow {
  position: absolute;
  width: 58vw;
  height: 58vw;
  left: 8vw;
  top: -34vw;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgba(61, 220, 151, 0.13),
    transparent 67%
  );
  animation: glow-breathe 12s ease-in-out infinite;
}
.ambient-orbit {
  position: absolute;
  border: 1px solid rgba(110, 231, 174, 0.11);
  border-radius: 50%;
  animation: orbit-drift 24s ease-in-out infinite alternate;
}
.orbit-one {
  width: 620px;
  height: 620px;
  right: -190px;
  top: -250px;
  box-shadow:
    0 0 0 74px rgba(113, 143, 219, 0.018),
    0 0 0 148px rgba(110, 231, 174, 0.012);
}
.orbit-two {
  width: 420px;
  height: 420px;
  left: -210px;
  bottom: -210px;
  animation-delay: -9s;
  animation-duration: 30s;
}
.ambient-signal {
  position: absolute;
  width: 100%;
  height: 76%;
  left: 0;
  bottom: -4%;
  overflow: visible;
  opacity: 0.52;
  animation: signal-float 18s ease-in-out infinite alternate;
}
.signal-line,
.signal-shadow {
  fill: none;
  stroke: url(#signal-gradient);
  stroke-width: 1.25;
  vector-effect: non-scaling-stroke;
}
.signal-shadow {
  stroke-width: 16;
  opacity: 0.06;
}
.signal-line {
  stroke-dasharray: 7 9;
  animation: signal-travel 28s linear infinite;
}
.ambient-signal circle {
  fill: var(--login-bg);
  stroke: var(--login-mint);
  stroke-width: 1.4;
  transform-box: fill-box;
  transform-origin: center;
  animation: node-pulse 5s ease-in-out infinite;
}
.ambient-signal circle:nth-of-type(2) {
  animation-delay: -1.6s;
}
.ambient-signal circle:nth-of-type(3) {
  animation-delay: -3.2s;
}
.landing-header,
.landing-content,
.landing-footer {
  position: relative;
  z-index: 1;
  width: min(1380px, 100%);
  margin-inline: auto;
}
.landing-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.landing-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--login-ink);
  text-decoration: none;
}
.landing-brand > span {
  font-size: 20px;
  font-weight: 790;
  letter-spacing: -0.055em;
}
.landing-brand > span span {
  color: var(--login-mint);
}
.private-installation {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 11px;
  border: 1px solid var(--login-line);
  border-radius: 99px;
  background: rgba(17, 29, 23, 0.48);
  color: #a8b8b0;
  font-size: 9px;
  font-weight: 650;
}
.private-installation i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--login-mint);
  box-shadow: 0 0 0 4px rgba(110, 231, 174, 0.08);
}
.landing-content {
  min-height: calc(100vh - 142px);
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(390px, 0.68fr);
  align-items: center;
  gap: clamp(55px, 8vw, 125px);
  padding-block: 48px 36px;
}
.landing-story {
  min-width: 0;
}
.story-copy {
  max-width: 720px;
}
.story-kicker {
  display: flex;
  align-items: center;
  gap: 11px;
  margin: 0 0 21px;
  color: #aebdb5;
  font-size: 9px;
  font-weight: 720;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.story-kicker span {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 1px solid rgba(110, 231, 174, 0.3);
  border-radius: 50%;
  color: var(--login-mint);
  font-size: 8px;
}
.story-copy h1 {
  max-width: 760px;
  margin: 0;
  font-size: clamp(45px, 5.35vw, 78px);
  line-height: 0.99;
  letter-spacing: -0.067em;
}
.story-copy h1 em {
  color: var(--login-mint);
  font-style: normal;
  font-weight: 540;
}
.story-intro {
  max-width: 610px;
  margin: 24px 0 0;
  color: #9aada3;
  font-size: clamp(14px, 1.25vw, 17px);
  line-height: 1.65;
}
.product-window {
  max-width: 690px;
  margin-top: 34px;
  overflow: hidden;
  border: 1px solid var(--login-line);
  border-radius: 19px;
  background: rgba(13, 24, 19, 0.62);
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.24);
  backdrop-filter: blur(18px);
}
.product-window > header {
  height: 42px;
  padding: 0 14px;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  border-bottom: 1px solid var(--login-line);
  color: var(--login-muted);
}
.product-window > header > div {
  display: flex;
  gap: 5px;
}
.window-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #3d4c44;
}
.product-window > header small {
  font-size: 8px;
}
.window-live {
  justify-self: end;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 7px;
}
.window-live i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--login-mint);
}
.window-body {
  padding: 19px 21px 16px;
}
.window-total {
  display: grid;
  gap: 3px;
}
.window-total small {
  color: var(--login-muted);
  font-size: 7px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.window-total strong {
  font-size: 20px;
  letter-spacing: -0.035em;
}
.window-total span {
  color: #778b80;
  font-size: 8px;
}
.window-chart {
  height: 84px;
  margin-top: -5px;
}
.window-chart svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}
.chart-area {
  fill: url(#area-gradient);
}
.chart-stroke {
  fill: none;
  stroke: var(--login-mint);
  stroke-width: 1.5;
  vector-effect: non-scaling-stroke;
}
.asset-ribbon {
  padding-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 9px 18px;
  border-top: 1px solid var(--login-line);
}
.asset-ribbon span {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #8fa299;
  font-size: 7px;
}
.asset-ribbon i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.asset-ribbon .mint {
  background: var(--login-mint);
}
.asset-ribbon .blue {
  background: var(--login-blue);
}
.asset-ribbon .violet {
  background: #9a78da;
}
.asset-ribbon .gold {
  background: #d5aa58;
}
.trust-list {
  max-width: 690px;
  margin: 25px 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  list-style: none;
}
.trust-list li {
  padding: 0 18px;
  border-left: 1px solid var(--login-line);
  display: grid;
  gap: 4px;
}
.trust-list li:first-child {
  padding-left: 0;
  border-left: 0;
}
.trust-list span {
  font-size: 9px;
  font-weight: 740;
}
.trust-list small {
  color: #75887e;
  font-size: 7px;
  line-height: 1.45;
}
.login-panel {
  width: 100%;
  max-width: 470px;
  justify-self: end;
}
.login-panel form {
  position: relative;
  overflow: hidden;
  padding: clamp(29px, 3.4vw, 43px);
  border: 1px solid rgba(198, 231, 214, 0.15);
  border-radius: 25px;
  background: var(--login-surface);
  box-shadow: 0 36px 100px rgba(0, 0, 0, 0.34);
  backdrop-filter: blur(22px);
}
.login-panel form::before {
  content: "";
  position: absolute;
  width: 160px;
  height: 160px;
  right: -80px;
  top: -100px;
  border-radius: 50%;
  background: rgba(110, 231, 174, 0.08);
  filter: blur(1px);
}
.login-panel header {
  position: relative;
}
.login-panel header p {
  margin: 0 0 8px;
  color: var(--login-mint);
  font-size: 8px;
  font-weight: 760;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.login-panel h2 {
  margin: 0;
  font-size: clamp(24px, 2.4vw, 32px);
  letter-spacing: -0.05em;
}
.login-panel header > span {
  display: block;
  margin-top: 8px;
  color: var(--login-muted);
  font-size: 10px;
}
.form-fields {
  margin-top: 28px;
  display: grid;
  gap: 17px;
}
.form-fields label {
  display: grid;
  gap: 7px;
}
.form-fields label > span {
  color: #b9c7c0;
  font-size: 9px;
  font-weight: 650;
}
.input-shell {
  height: 49px;
  padding: 0 13px;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(198, 231, 214, 0.16);
  border-radius: 12px;
  background: rgba(7, 15, 11, 0.62);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}
.input-shell:focus-within {
  border-color: rgba(110, 231, 174, 0.65);
  background: rgba(7, 15, 11, 0.8);
  box-shadow: 0 0 0 4px rgba(110, 231, 174, 0.07);
}
.input-shell > svg {
  width: 16px;
  flex: 0 0 auto;
  fill: none;
  stroke: #74877d;
  stroke-width: 1.4;
}
.input-shell input {
  min-width: 0;
  flex: 1;
  padding: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--login-ink);
  font-size: 11px;
}
.input-shell input::placeholder {
  color: #53645b;
}
.password-toggle {
  width: auto !important;
  padding: 5px !important;
  border: 0 !important;
  background: transparent !important;
  color: #8da198 !important;
  font-size: 8px !important;
  font-weight: 700 !important;
}
.login-error {
  margin-top: 15px;
  padding: 10px 11px;
  display: flex;
  align-items: center;
  gap: 9px;
  border: 1px solid rgba(255, 133, 133, 0.2);
  border-radius: 10px;
  background: rgba(255, 133, 133, 0.07);
  color: #ff9b9b;
}
.login-error > span {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: rgba(255, 133, 133, 0.13);
  font-size: 8px;
  font-weight: 800;
}
.login-error p {
  margin: 0;
  font-size: 8px;
}
.login-submit {
  width: 100%;
  height: 49px;
  margin-top: 21px;
  padding: 0 15px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 0;
  border-radius: 12px;
  background: var(--login-mint);
  color: #07120d;
  font-size: 10px;
  font-weight: 790;
  cursor: pointer;
  box-shadow: 0 13px 32px rgba(61, 220, 151, 0.15);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    opacity 0.2s ease;
}
.login-submit:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 17px 38px rgba(61, 220, 151, 0.22);
}
.login-submit:disabled {
  cursor: wait;
  opacity: 0.65;
}
.login-submit svg {
  width: 17px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
}
.login-panel form > footer {
  margin-top: 22px;
  padding-top: 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-top: 1px solid var(--login-line);
}
.security-mark {
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: rgba(110, 231, 174, 0.08);
  color: var(--login-mint);
}
.security-mark svg {
  width: 17px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.4;
}
.login-panel footer p {
  margin: 0;
  display: grid;
  gap: 2px;
}
.login-panel footer strong {
  font-size: 8px;
}
.login-panel footer small {
  color: #75887e;
  font-size: 7px;
}
.landing-footer {
  display: flex;
  justify-content: space-between;
  color: #5f7168;
  font-size: 7px;
  letter-spacing: 0.03em;
}
@keyframes glow-breathe {
  50% {
    transform: scale(1.08);
    opacity: 0.72;
  }
}
@keyframes orbit-drift {
  to {
    transform: translate3d(-24px, 18px, 0) scale(1.04);
  }
}
@keyframes signal-float {
  to {
    transform: translate3d(0, -14px, 0) scaleY(1.025);
  }
}
@keyframes signal-travel {
  to {
    stroke-dashoffset: -320;
  }
}
@keyframes node-pulse {
  50% {
    transform: scale(1.65);
    opacity: 0.6;
  }
}
@media (max-width: 980px) {
  .login-landing {
    padding-inline: 28px;
  }
  .landing-content {
    grid-template-columns: 1fr;
    gap: 42px;
    padding-top: 55px;
  }
  .landing-story {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(270px, 0.7fr);
    gap: 32px;
    align-items: end;
  }
  .story-copy {
    grid-column: 1/-1;
  }
  .product-window {
    margin: 0;
  }
  .trust-list {
    grid-template-columns: 1fr;
    margin: 0;
  }
  .trust-list li {
    padding: 11px 0;
    border-left: 0;
    border-top: 1px solid var(--login-line);
  }
  .login-panel {
    max-width: none;
  }
  .login-panel form {
    display: grid;
    grid-template-columns: 1fr 1.1fr;
    gap: 0 32px;
  }
  .login-panel header,
  .login-panel form > footer {
    grid-column: 1;
  }
  .form-fields,
  .login-error,
  .login-submit {
    grid-column: 2;
  }
  .form-fields {
    grid-row: 1/3;
    margin-top: 0;
  }
  .login-submit {
    align-self: end;
  }
  .login-panel form > footer {
    align-self: end;
  }
  .landing-footer {
    padding-top: 20px;
  }
}
@media (max-width: 680px) {
  .login-landing {
    padding: 21px 18px;
  }
  .private-installation {
    padding: 7px;
    font-size: 0;
  }
  .private-installation i {
    margin: 0;
  }
  .landing-content {
    padding: 46px 0 28px;
  }
  .landing-story {
    display: block;
  }
  .story-copy h1 {
    font-size: clamp(39px, 12vw, 56px);
  }
  .story-intro {
    font-size: 13px;
  }
  .product-window {
    margin-top: 29px;
  }
  .trust-list {
    margin-top: 20px;
  }
  .login-panel form {
    display: block;
    padding: 25px 21px;
    border-radius: 20px;
  }
  .form-fields {
    margin-top: 25px;
  }
  .login-panel form > footer {
    margin-top: 20px;
  }
  .landing-footer span:last-child {
    display: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .ambient-glow,
  .ambient-orbit,
  .ambient-signal,
  .signal-line,
  .ambient-signal circle {
    animation: none !important;
  }
}
@media (min-width: 981px) and (max-height: 800px) {
  .landing-content {
    padding-block: 28px 14px;
  }
  .product-window {
    margin-top: 26px;
  }
  .trust-list {
    margin-top: 18px;
  }
}
.landing-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.login-language-picker {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #a8b8b0;
  font-size: 9px;
}
.login-language-picker select {
  padding: 7px 24px 7px 9px;
  border: 1px solid var(--login-line);
  border-radius: 9px;
  background: #111d17;
  color: var(--login-ink);
  font: 650 10px inherit;
}
@media (max-width: 680px) {
  .login-language-picker > span {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
  }
}

/* Keep every visible login label and utility caption at or above 10 px. */
.private-installation,
.story-kicker,
.story-kicker span,
.product-window > header small,
.window-live,
.window-total small,
.window-total span,
.asset-ribbon span,
.trust-list span,
.trust-list small,
.login-panel header p,
.form-fields label > span,
.login-error > span,
.login-error p,
.login-panel footer strong,
.login-panel footer small,
.landing-footer,
.login-language-picker {
  font-size: 10px;
}
.password-toggle {
  font-size: 10px !important;
}
@media (max-width: 680px) {
  .private-installation {
    font-size: 0;
  }
}
</style>
