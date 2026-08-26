<script setup lang="ts">
defineProps<{
  collapsed: boolean;
  controls: string;
  label: string;
}>();

defineEmits<{ toggle: [] }>();
</script>

<template>
  <button
    type="button"
    class="fund-collapse-button investment-collapse-button"
    :class="{ collapsed }"
    :aria-expanded="!collapsed"
    :aria-controls="controls"
    :aria-label="label"
    :title="label"
    @click="$emit('toggle')"
  >
    <svg
      :data-direction="collapsed ? 'down' : 'up'"
      aria-hidden="true"
      viewBox="0 0 20 20"
    >
      <path :d="collapsed ? 'm5 7.5 5 5 5-5' : 'm5 12.5 5-5 5 5'" />
    </svg>
  </button>
</template>

<style scoped>
.investment-collapse-button {
  width: 36px;
  height: 36px;
  padding: 0;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid var(--fz-line);
  border-radius: 10px;
  background: var(--fz-surface-soft);
  color: var(--fz-muted);
  cursor: pointer;
}

.investment-collapse-button:hover {
  border-color: var(--fz-accent);
  color: var(--fz-ink);
}

.investment-collapse-button:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 2px;
}

.investment-collapse-button svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}
</style>
