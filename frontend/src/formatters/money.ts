import { i18n, reportingCurrency } from "../i18n";

function formatter(options: Intl.NumberFormatOptions) {
  return {
    format(value: number | bigint) {
      return new Intl.NumberFormat(i18n.global.locale.value, options).format(
        value,
      );
    },
  };
}

export const money = {
  format(value: number | bigint, currency = reportingCurrency.value) {
    return new Intl.NumberFormat(i18n.global.locale.value, {
      style: "currency",
      currency,
    }).format(value);
  },
};
/** @deprecated Use ``money``; retained for compatibility with external extensions. */
export const eur = money;
export const percent = formatter({
  style: "percent",
  maximumFractionDigits: 2,
});
