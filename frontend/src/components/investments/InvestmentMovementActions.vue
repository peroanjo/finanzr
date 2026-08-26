<script setup lang="ts">
defineProps<{
  editLabel: string;
  deleteLabel: string;
}>();

defineEmits<{
  edit: [];
  delete: [];
}>();
</script>

<template>
  <span class="movement-row-actions investment-movement-actions">
    <button
      type="button"
      class="investment-movement-action investment-movement-action--edit"
      :aria-label="editLabel"
      :title="editLabel"
      @click="$emit('edit')"
    >
      <svg aria-hidden="true" viewBox="0 0 20 20">
        <path d="m13.5 3.5 3 3L7 16l-4 1 1-4 9.5-9.5Z" />
        <path d="m11.5 5.5 3 3" />
      </svg>
    </button>
    <button
      type="button"
      class="investment-movement-action investment-movement-action--delete delete-order"
      :aria-label="deleteLabel"
      :title="deleteLabel"
      @click="$emit('delete')"
    >
      <svg aria-hidden="true" viewBox="0 0 20 20">
        <path d="M4 6h12M8 3h4l1 3H7l1-3Z" />
        <path d="m6 6 .7 11h6.6L14 6M8.5 9v5M11.5 9v5" />
      </svg>
    </button>
  </span>
</template>

<style scoped>
.investment-movement-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.investment-movement-action {
  width: 30px;
  height: 30px;
  padding: 0;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid var(--fz-line);
  border-radius: 8px;
  background: transparent;
  color: var(--fz-muted);
  cursor: pointer;
}

.investment-movement-action svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.7;
}

.investment-movement-action:hover {
  border-color: var(--fz-accent);
  background: color-mix(in srgb, var(--fz-accent) 8%, transparent);
  color: var(--fz-ink);
}

.investment-movement-action:focus-visible {
  outline: 2px solid var(--fz-accent);
  outline-offset: 2px;
}

.investment-movement-action--delete {
  border-color: color-mix(in srgb, var(--fz-negative) 32%, var(--fz-line));
  color: var(--fz-negative);
}

.investment-movement-action--delete:hover {
  border-color: var(--fz-negative);
  background: color-mix(in srgb, var(--fz-negative) 10%, transparent);
  color: var(--fz-negative);
}

.investment-movement-action--delete:focus-visible {
  outline-color: var(--fz-negative);
}
</style>
