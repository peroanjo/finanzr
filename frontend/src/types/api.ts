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
  id: number;
  nombre: string;
  plataforma: string;
  estado: string;
  capital_inicial: number;
  capital_nuevo: number;
  capital_devuelto: number;
  beneficio_obtenido: number;
  beneficio_obtenido_neto?: number;
  beneficio_estimado: number | null;
  beneficio_estimado_neto?: number;
  tir: number;
  meses: number;
  fecha_inicio: string;
  fecha_vencimiento: string;
  fecha_devolucion: string;
  movimientos: RealEstateMovement[];
  origen: string;
  retencion_irpf?: number | null;
  moneda: string;
}
export interface RealEstateMovement {
  id: string;
  tipo: "capital_return" | "profit";
  fecha: string;
  importe: number;
  nota: string;
  retencion_irpf_aplicada?: number | null;
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
  id: number;
  nombre: string;
  plataforma: string;
  importer_slug: string;
  importer_name: string;
  moneda?: string;
}
export interface CryptoOrder {
  operacion_id: string;
  fecha_operacion: string;
  titulos: number;
  importe_neto: number;
  cuenta_id: number;
  cuenta_nombre?: string;
  plataforma?: string;
  tipo_operacion: string;
  symbol: string;
  nombre_activo: string;
  precio_compra: number;
  comision: number;
  moneda?: string;
  moneda_base?: string;
  importe_base?: number;
  precio_base?: number;
  comision_base?: number;
  tipo_cambio?: number;
  fecha_tipo_cambio?: string;
  fuente_tipo_cambio?: string;
}
export interface CryptoInstrument {
  symbol: string;
  ticker: string;
  nombre: string;
  moneda?: string;
}
export interface CryptoPrice {
  symbol: string;
  precio: number;
  updated: string;
  moneda: string;
  moneda_base?: string;
  precio_orig: number;
}
export interface MarketCandle {
  fecha: string;
  precio: number;
  open: number;
  high: number;
  low: number;
  close: number;
  moneda_base?: string;
}
export interface CryptoChartResponse {
  symbol: string;
  ticker: string;
  moneda: string;
  moneda_base?: string;
  range: string;
  data: MarketCandle[];
}
export interface CryptoPerformancePoint {
  fecha: string;
  valor: number;
  invertido: number;
  pnl: number;
  pnl_pct: number;
}
export interface CryptoPerformanceResponse {
  range: string;
  cuenta_id: string | number;
  moneda?: string;
  moneda_base?: string;
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
  id: number;
  nombre: string;
  plataforma: string;
  importer_slug: string;
  importer_name: string;
  moneda?: string;
}
export interface StockOrder {
  operacion_id: string;
  fecha_operacion: string;
  titulos: number;
  importe_neto: number;
  cuenta_id: number;
  cuenta_nombre?: string;
  plataforma?: string;
  tipo_operacion: string;
  isin: string;
  nombre_activo: string;
  precio_compra: number;
  comision: number;
  es_saveback: boolean;
  moneda?: string;
  moneda_base?: string;
  importe_base?: number;
  precio_base?: number;
  comision_base?: number;
  tipo_cambio?: number;
  fecha_tipo_cambio?: string;
  fuente_tipo_cambio?: string;
}
export interface StockInstrument {
  isin: string;
  ticker: string;
  nombre: string;
  moneda?: string;
}
export interface StockPrice {
  isin: string;
  precio: number;
  updated: string;
  moneda: string;
  moneda_base?: string;
  precio_orig: number;
}
export interface StockChartResponse {
  isin: string;
  ticker: string;
  moneda: string;
  moneda_base?: string;
  range: string;
  data: MarketCandle[];
}
export interface StockPerformancePoint {
  fecha: string;
  valor: number;
  invertido: number;
  pnl: number;
  pnl_pct: number;
}
export interface StockPerformanceResponse {
  range: string;
  cuenta_id: string | number;
  moneda?: string;
  moneda_base?: string;
  data: StockPerformancePoint[];
}
export interface FundAccount {
  id: number;
  nombre: string;
  tipo: string;
  plataforma: string;
  importer_slug: string;
  importer_name: string;
  moneda?: string;
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
export interface FundOrder {
  operacion_id: string;
  fecha_operacion: string;
  fecha_liquidacion: string;
  tipo_operacion: string;
  isin: string;
  nombre_fondo: string;
  titulos: number;
  precio_neto: number;
  importe_neto: number;
  cuenta_id: number;
  cuenta_nombre?: string;
  plataforma?: string;
  divisa?: string;
  moneda?: string;
  moneda_base?: string;
  importe_base?: number;
  precio_base?: number;
  tipo_cambio?: number;
  fecha_tipo_cambio?: string;
  fuente_tipo_cambio?: string;
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
  cuenta_id: string | number;
  moneda?: string;
  moneda_base?: string;
  data: FundPerformancePoint[];
}
export interface FundInstrument {
  isin: string;
  ticker: string;
  nombre: string;
  tipo: string;
  subtipo: string;
  moneda?: string;
}
export interface FundPrice {
  isin: string;
  precio: number;
  updated: string;
  moneda?: string;
  moneda_base?: string;
  precio_orig?: number;
}
export interface FundPricePoint {
  fecha: string;
  precio: number;
  precio_orig?: number;
  precio_base?: number;
}
export interface FundChartResponse {
  isin: string;
  ticker: string;
  moneda: string;
  moneda_base?: string;
  range: string;
  data: FundPricePoint[];
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
