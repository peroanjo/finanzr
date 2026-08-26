<script setup lang="ts">
defineProps<{ label: string }>();

defineEmits<{ add: [] }>();
</script>

<template>
  <button
    type="button"
    class="investment-add-asset-button"
    :aria-label="label"
    :title="label"
    @click="$emit('add')"
  >
    <svg aria-hidden="true" viewBox="0 0 20 20">
      <path d="M10 4v12M4 10h12" />
    </svg>
    <span>{{ label }}</span>
  </button>
</template>

<style scoped>
.investment-add-asset-button {
  height: 36px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  flex: 0 0 auto;
  border: 1px solid color-mix(in srgb, var(--fz-accent) 58%, var(--fz-line));
  border-radius: 10px;
  background: color-mix(in srgb, var(--fz-accent) 12%, var(--fz-surface));
  color: var(--fz-accent);
  font-size: 11px;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  transition:
    border-color 120ms ease,
    background-color 120ms ease,
    color 120ms ease,
    transform 120ms ease;
}

.investment-add-asset-button svg {
  width: 18px;
  height: 18px;
  flex: 0 0 auto;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-width: 1.9;
}

.investment-add-asset-button:hover {
  border-color: var(--fz-accent);
  background: color-mix(in srgb, var(--fz-accent) 19%, var(--fz-surface));
  color: var(--fz-ink);
  transform: translateY(-1px);
}

.investment-add-asset-button:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 2px;
}
</style>
