<script setup lang="ts">
defineProps<{ name: string }>();
</script>

<template>
  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <template v-if="name === 'home'">
      <path d="M3.5 10.5 12 3.75l8.5 6.75" />
      <path d="M5.5 9.25v10h13v-10M9.5 19.25v-6h5v6" />
    </template>
    <template v-else-if="name === 'wallet'">
      <path
        d="M4 6.5h14.5A1.5 1.5 0 0 1 20 8v10H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h12"
      />
      <path d="M15 11h5v4h-5a2 2 0 0 1 0-4Z" />
    </template>
    <template v-else-if="name === 'trend'">
      <path d="M3 18 9 12l4 4 8-9" />
      <path d="M15 7h6v6" />
    </template>
    <template v-else-if="name === 'briefcase'">
      <rect x="3" y="7" width="18" height="12" rx="2" />
      <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" />
    </template>
    <template v-else-if="name === 'building'">
      <path d="M4 21V5l8-3v19M12 7h8v14M2 21h20" />
      <path d="M7 7h2m-2 4h2m-2 4h2m7-4h1m-1 4h1" />
    </template>
    <template v-else-if="name === 'funds'">
      <path d="M12 3a9 9 0 1 0 9 9h-9V3Z" />
      <path d="M15 3.5A8.5 8.5 0 0 1 20.5 9H15V3.5Z" />
    </template>
    <template v-else-if="name === 'stocks'">
      <path d="M6 4v16M18 3v18M12 7v10" />
      <path d="M3.5 8h5v7h-5zM9.5 9h5v5h-5zM15.5 6h5v9h-5z" />
    </template>
    <template v-else-if="name === 'crypto'">
      <path d="M9 5h5.5a3 3 0 0 1 0 6H9m0 0h6a3.5 3.5 0 0 1 0 7H9V5" />
      <path d="M11 2v3m4-3v3m-4 13v4m4-4v4M6 5h3m-3 13h3" />
    </template>
    <template v-else-if="name === 'currency'">
      <path d="M7 10h14l-4-4" />
      <path d="M17 14H3l4 4" />
    </template>
    <template v-else-if="name === 'settings'">
      <circle cx="12" cy="12" r="3" />
      <path
        d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.08A1.7 1.7 0 0 0 9 19.37a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.63 15a1.7 1.7 0 0 0-1.56-1.03H3v-4h.08A1.7 1.7 0 0 0 4.63 9a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.63a1.7 1.7 0 0 0 1.03-1.56V3h4v.08A1.7 1.7 0 0 0 15 4.63a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.37 9a1.7 1.7 0 0 0 1.56 1.03H21v4h-.08A1.7 1.7 0 0 0 19.4 15Z"
      />
    </template>
    <template v-else-if="name === 'import'">
      <path d="M12 3v12m0 0 4-4m-4 4-4-4" />
      <path d="M5 16v4h14v-4" />
    </template>
    <template v-else-if="name === 'user'">
      <circle cx="12" cy="8" r="4" />
      <path d="M4.5 21a7.5 7.5 0 0 1 15 0" />
    </template>
    <template v-else-if="name === 'admin'">
      <path d="M12 3 20 6v5c0 5-3.4 8.2-8 10-4.6-1.8-8-5-8-10V6l8-3Z" />
      <path d="m9 12 2 2 4-4" />
    </template>
    <template v-else-if="name === 'interface'">
      <rect x="3" y="4" width="18" height="13" rx="2" />
      <path d="M8 21h8M12 17v4M7 9h10M9 12h6" />
    </template>
    <template v-else-if="name === 'tax' || name === 'withholdings'">
      <line x1="19" y1="5" x2="5" y2="19" />
      <circle cx="6.5" cy="6.5" r="2.5" />
      <circle cx="17.5" cy="17.5" r="2.5" />
    </template>
    <template v-else>
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M8 7h8M8 11h2m4 0h2M8 15h2m4 0h2M8 18h2m4 0h2" />
    </template>
  </svg>
</template>

<style scoped>
svg {
  width: 18px;
  height: 18px;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>
