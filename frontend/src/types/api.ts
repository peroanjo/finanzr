export interface Workspace {
  id: string;
  name: string;
  slug: string;
  base_currency: string;
  role: "owner" | "editor" | "viewer";
}
export interface UserSession {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "user" | "demo";
  active_workspace_id: string | null;
  workspaces: Workspace[];
  language: "es-ES" | "en";
  preferred_language: "es-ES" | "en" | null;
  default_language: "es-ES" | "en";
  default_crowdfunding_tax_rate?: number;
  summary_sources?: SummarySourceKey[];
  summary_sources_scope?: "personal" | "installation";
  default_summary_sources?: SummarySourceKey[];
  summary_source_keys?: SummarySourceKey[];
}
export type SummarySourceKey =
  | "savings"
  | "manual_investments"
  | "funds"
  | "stocks"
  | "crypto"
  | "crowdfunding"
  | "manual_assets";
export interface ImporterFormat {
  extension: string;
  label: string;
  description: string;
}
export interface ImporterField {
  name: string;
  label: string;
  description: string;
  example: string;
  required: boolean;
  position: number | null;
}
export interface ImporterCatalogItem {
  slug: string;
  display_name: string;
  target: string;
  target_label: string;
  description: string;
  source_instructions: string;
  input_kind: "text" | "records";
  accepted_extensions: string[];
  required_fields: string[];
  formats: ImporterFormat[];
  fields: ImporterField[];
  rules: string[];
}
export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "user" | "demo";
  is_active: boolean;
  is_self: boolean;
  date_joined: string;
  last_login: string | null;
}
export interface Summary {
  total_savings: number;
  total_investments: number;
  total_real_estate: number;
  net_worth: number;
  net_worth_change: number;
  total_interest: number;
  summary_sources?: SummarySourceKey[];
  summary_sources_scope?: "personal" | "installation";
  source_breakdown?: Array<{
    key: SummarySourceKey;
    value: number;
    included: boolean;
  }>;
}
export interface NetWorthPoint {
  fecha: string;
  ahorro: number;
  ahorro_intereses: number;
  balances: number;
  balance_aportes: number;
  inversiones: number;
  total: number;
  inv_aportes: number;
  source_totals?: Partial<Record<SummarySourceKey, number>>;
  source_contributions?: Partial<Record<SummarySourceKey, number>>;
}
export interface RealEstateInvestment {
  id: string;
  name: string;
  platform: string;
  status: "active" | "completed" | "defaulted" | "cancelled";
  initial_capital: number;
  new_capital: number;
  returned_capital: number;
  realized_profit: number;
  net_realized_profit: number;
  expected_profit: number | null;
  net_expected_profit: number;
  expected_irr_percent: number;
  expected_term_months: number;
  start_date: string;
  maturity_date: string | null;
  return_date: string | null;
  movements: RealEstateMovement[];
  origin: string;
  tax_rate: number | null;
  currency: string;
}
export interface RealEstateMovement {
  id: string;
  flow_type: "capital_return" | "profit";
  effective_date: string | null;
  amount: number;
  note: string;
  applied_tax_rate: number | null;
}
export interface PortfolioAnalysisItem {
  id: string;
  nombre: string;
  identificador: string;
  clase: string;
  subtipo: string;
  cuenta: string;
  cuenta_id: string;
  plataforma: string;
  valor: number;
  peso: number;
  origen: "fund" | "stock" | "crypto" | "real_estate" | "manual";
}
export interface PortfolioAnalysisResponse {
  total: number;
  items: PortfolioAnalysisItem[];
}
export interface ManualAsset {
  id: string;
  name: string;
  asset_class: string;
  subtype: string;
  platform: string;
  value: number;
  currency: string;
}
export interface ManualAssetRequest {
  name: string;
  asset_class: string;
  subtype?: string;
  platform?: string;
  value: number;
}
export interface SavingsAccount {
  id: string;
  name: string;
  bank: string;
  type: string;
  currency: string;
}
export interface SavingsSnapshot {
  id: string;
  account_id: string;
  date: string;
  balance: number;
  balance_original: number;
  contribution: number;
  contribution_original: number;
  interest: number;
  interest_original: number;
  currency: string;
  base_currency: string;
  exchange_rate: number;
  exchange_rate_date: string;
  exchange_rate_source: string;
}
export interface AccountChartSeries {
  label: string;
  color: string;
  values: number[];
}
export interface InvestmentAccount {
  id: string;
  name: string;
  platform: string;
  type: string;
  currency: string;
}
export interface InvestmentSnapshot {
  id: string;
  account_id: string;
  date: string;
  value: number;
  value_original: number;
  contribution: number;
  contribution_original: number;
  interest: number;
  interest_original: number;
  currency: string;
  base_currency: string;
  exchange_rate: number;
  exchange_rate_date: string;
  exchange_rate_source: string;
}
export interface CryptoPosition {
  symbol: string;
  nombre: string;
  titulos: number;
  coste_total: number;
  precio_actual: number | null;
  valor_actual: number | null;
  pnl: number | null;
  pnl_realizada: number;
  moneda?: string;
  moneda_base?: string;
}
export interface CryptoAccount {
  id: string;
  name: string;
  platform: string;
  type: string;
  currency: string;
  importer_slug: string;
  importer_name: string;
}
export type TransactionOperationType =
  "buy" | "sell" | "transfer_in" | "transfer_out";
export type TransactionCashFlowType =
  "contribution" | "withdrawal" | "internal" | "none";
interface TransactionDtoBase {
  id: string;
  account_id: string;
  account_name: string;
  platform: string;
  asset_name: string;
  trade_date: string;
  settlement_date: string | null;
  operation_type: TransactionOperationType;
  cash_flow_type: TransactionCashFlowType;
  quantity: number;
  unit_price: number;
  net_amount: number;
  fee: number;
  currency: string;
  base_currency: string;
  base_unit_price: number | null;
  base_net_amount: number | null;
  base_fee: number | null;
  fx_rate_to_base: number | null;
  fx_rate_date: string | null;
  fx_source: string;
  market: string;
  provider_operation_type: string;
}
export interface CryptoOrder extends TransactionDtoBase {
  symbol: string;
}
export type InstrumentKind = "fund" | "stock" | "etf" | "crypto";
export type InstrumentIdentifierScheme =
  "isin" | "yahoo" | "crypto_symbol" | "kraken" | "other";
export interface InstrumentIdentifier {
  scheme: InstrumentIdentifierScheme;
  value: string;
  venue: string;
  is_primary: boolean;
}
export interface Instrument {
  id: string;
  kind: InstrumentKind;
  name: string;
  quote_currency: string;
  identifiers: InstrumentIdentifier[];
  asset_class: string | null;
  subtype: string | null;
  is_active: boolean;
}
export interface CryptoInstrument extends Instrument {
  kind: "crypto";
}
export interface MarketPrice {
  id: string;
  instrument_id: string;
  quoted_at: string;
  close: number;
  currency: string;
  base_close: number;
  base_currency: string;
  fx_rate_to_base: number;
  fx_rate_date: string;
  fx_source: string;
  source: string;
}
export type CryptoPrice = MarketPrice;
/** Internal chart point shape consumed by the existing chart components. */
export interface MarketCandle {
  fecha: string;
  precio: number;
  open: number;
  high: number;
  low: number;
  close: number;
  moneda_base?: string;
}
export interface MarketChartCandle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
}
export interface MarketChartResponse {
  instrument_id: string;
  ticker: string;
  currency: string;
  base_currency: string;
  range: string;
  data: MarketChartCandle[];
}
export type CryptoChartResponse = MarketChartResponse;
export interface CryptoPerformancePoint {
  fecha: string;
  valor: number;
  invertido: number;
  pnl: number;
  pnl_pct: number;
}
export interface CryptoPerformanceResponse {
  range: string;
  account_id: string;
  kind?: string;
  moneda_base: string;
  data: CryptoPerformancePoint[];
}
export interface StockPosition {
  isin: string;
  nombre: string;
  titulos: number;
  coste_total: number;
  precio_actual: number | null;
  valor_actual: number | null;
  pnl: number | null;
  pnl_realizada: number;
  moneda?: string;
  moneda_base?: string;
}
export interface StockAccount {
  id: string;
  name: string;
  platform: string;
  type: string;
  currency: string;
  importer_slug: string;
  importer_name: string;
}
export interface StockOrder extends TransactionDtoBase {
  isin: string;
  is_saveback: boolean;
}
export interface StockInstrument extends Instrument {
  kind: "stock" | "etf";
}
export type StockPrice = MarketPrice;
export type StockChartResponse = MarketChartResponse;
export interface StockPerformancePoint {
  fecha: string;
  valor: number;
  invertido: number;
  pnl: number;
  pnl_pct: number;
}
export interface StockPerformanceResponse {
  range: string;
  account_id: string;
  kind?: string;
  moneda_base: string;
  data: StockPerformancePoint[];
}
export interface FundAccount {
  id: string;
  name: string;
  platform: string;
  type: string;
  currency: string;
  importer_slug: string;
  importer_name: string;
}
export interface FundPosition {
  isin: string;
  nombre: string;
  tipo: string;
  subtipo: string;
  total_invertido: number;
  participaciones: number;
  precio_medio: number;
  precio_actual: number | null;
  valor_actual: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  moneda?: string;
  moneda_base?: string;
}
export interface FundOrder extends TransactionDtoBase {
  isin: string;
}
export interface FundPerformancePoint {
  fecha: string;
  valor: number;
  invertido: number;
  pnl: number;
  pnl_pct: number;
}
export interface FundPerformanceResponse {
  range: string;
  account_id: string;
  kind?: string;
  moneda_base: string;
  data: FundPerformancePoint[];
}
export interface FundInstrument extends Instrument {
  kind: "fund";
}
export type FundPrice = MarketPrice;
export interface PriceFetchResult {
  instrument_id: string;
  base_close: number | null;
  close: number | null;
  currency: string | null;
  ticker: string | null;
  error: string | null;
}
export interface PriceFetchResponse {
  results: PriceFetchResult[];
}
export interface FundPricePoint {
  fecha: string;
  precio: number;
  precio_orig?: number;
  precio_base?: number;
}
export interface FundChartPoint {
  date: string;
  close: number;
}
export interface FundChartResponse {
  instrument_id: string;
  ticker: string;
  currency: string;
  base_currency: string;
  range: string;
  data: FundChartPoint[];
}
export interface FxRateItem {
  id: string;
  quote_currency: string;
  base_currency: string;
  rate_date: string;
  rate: number;
  source: string;
  scope?: "provider" | "workspace";
}
export interface FxRatePayload {
  quote_currency: string;
  base_currency: string;
  rate_date: string;
  rate: number;
  source?: string;
}
export interface FxRateChartPoint {
  fecha: string;
  rate: number;
}
export interface FxRateChartResponse {
  from_currency: string;
  to_currency: string;
  range: "1m" | "6m" | "1y" | "2y" | "custom";
  data: FxRateChartPoint[];
}
export interface FxConvertResult {
  from_currency: string;
  to_currency: string;
  original_amount: number;
  converted_amount: number;
  rate: number;
  rate_date: string;
  source: string;
}
export interface FetchFxRatesResult {
  ok: boolean;
  updated_count: number;
  errors: string[];
}
export type ApiRow = Record<string, string | number | boolean | null>;
