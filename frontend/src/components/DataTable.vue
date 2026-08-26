<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { ApiRow } from "../types/api";

const props = defineProps<{ rows: ApiRow[]; empty?: string }>();
const { t } = useI18n();
const columns = computed(() =>
  props.rows.length ? Object.keys(props.rows[0]) : [],
);
</script>

<template>
  <div class="table-wrap">
    <table v-if="rows.length">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">
            {{ column.replaceAll("_", " ") }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, index) in rows"
          :key="String(row.id ?? row.isin ?? row.symbol ?? index)"
        >
          <td v-for="column in columns" :key="column">{{ row[column] }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">{{ empty ?? t("shared.dataTable.empty") }}</p>
  </div>
</template>
