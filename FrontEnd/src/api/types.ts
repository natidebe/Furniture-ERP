// API types. Most come from the OpenAPI schema (schema.d.ts, regenerate with `npm run gen:api`
// while the backend runs). The rest are shapes the schema leaves untyped (nested lines, reports,
// the dashboard), written from the backend serializers.
import type { components } from './schema'

type S = components['schemas']

export type Role = S['RoleEnum']
export type Permission = S['PermissionsEnum']
export type Condition = S['StockConditionEnum']

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type Me = S['Me']
export type Location = S['Location']
export type Category = S['Category']
export type Unit = S['Unit']
export type Product = S['Product']
export type PriceHistory = S['PriceHistory']
export type Customer = S['Customer'] & { outstanding: string; over_limit: boolean }
export type CustomerBalance = S['CustomerBalance']
export type Statement = S['Statement']
export type StatementRow = S['StatementRow']
export type PaymentAccount = S['PaymentAccount']
export type User = S['User']
export type AuditLog = S['AuditLog']
export type SystemSettings = S['SystemSettings'] & { updated_by_name?: string | null }
export type ConditionChange = S['ConditionChange']
export type Movement = S['Movement']
export type LocationStock = S['LocationStock']
export type StockRow = S['StockRow']

export interface PermissionInfo {
  codename: Permission
  label: string
  default_for_roles: Role[]
}

export interface StockSummary extends Paginated<StockRow> {
  locations: { id: number; code: string; name: string }[]
}

export interface ProductStock {
  product: number
  code: string
  name: string
  selling_price: string
  min_stock: number
  stock: Record<string, LocationStock>
  in_transit: number
  total: number
  total_new: number
  low_stock: boolean
  locations: { id: number; code: string; name: string }[]
}

export interface GoodsReceipt {
  id: number
  number: string
  location: number
  location_code: string
  reference: string
  received_at: string
  received_by: number
  received_by_name: string
  note: string
  lines: { product: number; product_code: string; product_name: string; qty: number }[]
}

export interface Adjustment {
  id: number
  number: string
  location: number
  location_code: string
  product: number
  product_code: string
  qty_delta: number
  condition: Condition
  reason: string
  note: string
  status: 'proposed' | 'approved' | 'rejected'
  proposed_by: number
  proposed_by_name: string
  proposed_at: string
  decided_by: number | null
  decided_by_name: string | null
  decided_at: string | null
  decision_note: string
  movement_number: string | null
}

export interface TransferLine {
  id: number
  product: number
  product_code: string
  product_name: string
  condition: Condition
  qty_sent: number
  qty_received: number | null
}

export interface Transfer {
  id: number
  number: string
  from_location: number
  from_location_code: string
  to_location: number
  to_location_code: string
  status: 'in_transit' | 'received'
  transaction_number: string
  stock_request: number | null
  sent_by: number
  sent_by_name: string
  sent_at: string
  received_by: number | null
  received_by_name: string | null
  received_at: string | null
  discrepancy_note: string
  note: string
  lines: TransferLine[]
}

export interface RequestLine {
  id: number
  product: number
  product_code: string
  product_name: string
  qty_requested: number
  qty_released: number
  qty_remaining: number
}

export interface RequestRelease {
  id: number
  number: string
  transaction_number: string
  destination_type: 'branch' | 'customer_pickup'
  transfer_number: string | null
  released_by: number
  released_by_name: string
  released_at: string
  note: string
  lines: { product: number; product_code: string; qty: number }[]
}

export type RequestStatus = S['StockRequestStatusEnum']

export interface StockRequest {
  id: number
  number: string
  transaction_number: string
  status: RequestStatus
  created_at: string
  requesting_location: number
  requesting_location_code: string
  source_location: number
  source_location_code: string
  customer: number | null
  customer_name: string | null
  reference: string
  salesperson: number
  salesperson_name: string
  notes: string
  acknowledged_by: number | null
  acknowledged_at: string | null
  closed_by: number | null
  closed_at: string | null
  close_reason: string
  lines: RequestLine[]
  releases: RequestRelease[]
}

export interface OrderLine {
  id: number
  product: number
  product_code: string
  product_name: string
  condition: Condition
  qty: number
  unit_price: string
  discount: string
  line_total: string
  source_location_code: string
  qty_released: number
  qty_awaiting: number
  qty_returned: number
  paid: string | null
  remaining: string
}

export interface DeliveryNoteSummary {
  id: number
  number: string
  location_code: string
  issued_by_name: string
  issued_at: string
  issued_at_ec: string
  lines: { product_code: string; product_name: string; qty: number }[]
}

export interface OrderReturn {
  id?: number
  number: string
  amount?: string
  reason?: string
  created_at?: string
  [key: string]: unknown
}

export interface Order {
  id: number
  number: string
  customer: number
  customer_name: string
  customer_type: string
  branch: number
  branch_code: string
  salesperson: number
  salesperson_name: string
  channel: 'walk_in' | 'phone'
  receipt_type: 'official' | 'none'
  fulfillment_status: string
  payment_status: 'unpaid' | 'partial' | 'paid'
  total: string
  paid: string
  remaining: string
  notes: string
  created_at: string
  created_at_ec: string
  confirmed_at: string | null
  closed_at: string | null
  close_reason: string
  replaces: string | null
  replaced_by: string | null
  lines?: OrderLine[]
  delivery_notes?: DeliveryNoteSummary[]
  stock_requests?: { id: number; number: string; status: RequestStatus; [key: string]: unknown }[]
  returns?: OrderReturn[]
}

export interface Allocation {
  order: number
  order_number: string
  line: number | null
  product_code: string | null
  amount: string | null
  is_active: boolean
  deactivated_reason: string
}

export interface Payment {
  id: number
  number: string
  customer: number
  customer_name: string
  amount: string | null
  unallocated: string | null
  account: number | null
  account_name: string | null
  account_kind: 'organization' | 'personal'
  method: string
  receipt_number: string | null
  paid_at: string
  status: 'unverified' | 'verified' | 'rejected' | 'reversed'
  recorded_by: number
  recorded_by_name: string
  recorded_at: string
  verified_by: number | null
  verified_at: string | null
  closed_by: number | null
  closed_at: string | null
  close_reason: string
  replaces: string | null
  replaced_by: string | null
  note: string
  hidden: boolean
  allocations: Allocation[]
}

export interface DeliveryNote {
  id: number
  number: string
  order: number
  location: number
  issued_by: number
  issued_at: string
  [key: string]: unknown
}

export interface HistoryEvent {
  at: string
  at_ec: string
  event: string
  by: string
  detail: string
  number?: string
  reason?: string
}

export interface TransactionHistory {
  header: {
    transaction: string
    kind: string
    customer?: string | null
    salesperson?: string | null
    branch?: string | null
    status?: string
    payment_status?: string
    receipt_type?: string
    total?: string
    paid?: string | null
    remaining?: string
    replaces?: string | null
    products?: { code: string; name: string; qty: number; released?: number; returned?: number; source?: string }[]
    [key: string]: unknown
  }
  events: HistoryEvent[]
}

type Row = Record<string, unknown>
export interface SearchResult {
  query: string
  exact: { kind: string; id: number; number: string } | null
  products: { id: number; code: string; name: string; selling_price: string; wholesale_price: string | null; stock: Record<string, number>; in_transit: number; total: number }[]
  customers: { id: number; name: string; shop_name: string; phone: string; city: string; type: string; outstanding: string }[]
  orders: { id: number; number: string; customer: string; salesperson: string; branch: string; total: string; status: string; payment_status: string; created_at: string }[]
  delivery_notes: (Row & { id: number; number: string })[]
  stock_requests: (Row & { id: number; number: string })[]
  payments: (Row & { id: number; number: string })[]
}

export interface Block<T> {
  count: number
  items: T[]
}

export interface DashboardRequest {
  id: number
  number: string
  status: RequestStatus
  branch: string
  source: string
  customer: string | null
  salesperson: string
  created_at: string
  date_ec: string
  lines: string
}

export interface DashboardTransfer {
  id: number
  number: string
  from: string
  to: string
  status: string
  sent_at: string
  date_ec: string
  transaction: string
  short: boolean
  received_at?: string
  discrepancy_note?: string
}

export interface DashboardOrder {
  id: number
  number: string
  customer: string
  branch: string
  salesperson: string
  total: string
  payment_status: string
  fulfillment_status: string
  date_ec: string
}

export interface TodaySales {
  period_label: string
  sales: string
  returns: string
  net_sales: string
  transactions: number
  paid: string
  credit: string
  received: { organization: string; personal: string | null; combined: string | null }
  by_branch?: { branch: string; sales: string; transactions: number }[]
  by_salesperson?: { salesperson: string; sales: string; transactions: number }[]
}

export interface LowStockItem {
  id: number
  code: string
  name: string
  sellable: number
  min_stock: number
  shortfall: number
}

export interface Dashboard {
  role: Role
  // salesperson
  sales_today?: TodaySales
  waiting_for_payment?: Block<DashboardOrder>
  open_requests?: Block<DashboardRequest>
  transfers_arriving?: Block<DashboardTransfer>
  held_for_customers?: Block<{ order_id: number; order: string; customer: string; product: string; qty: number }>
  // storekeeper
  request_queue?: Block<DashboardRequest> & { by_status?: Record<string, number> }
  recent_movements?: Block<{
    id: number; number: string; type: string; condition: string; product: string; qty: number
    from: string | null; to: string | null; occurred_at: string; date_ec: string; transaction: string
  }>
  transfers_not_received?: Block<DashboardTransfer>
  low_stock?: Block<LowStockItem>
  // accountant / admin
  payments_to_verify?: Block<{
    id: number; number: string; paid_at: string; date_ec: string; customer: string; amount: string
    account: string; kind: 'organization' | 'personal'; receipt_number: string | null; recorded_by: string
  }> & { total: string }
  today?: TodaySales
  adjustments_to_approve?: Block<{
    id: number; number: string; location: string; product: string; qty_delta: number
    condition: string; reason: string; proposed_by: string; proposed_by_id: number; date_ec: string
  }>
  transfers_with_shortages?: Block<DashboardTransfer>
  customers_over_limit?: Block<{
    id: number; name: string; shop_name: string; phone: string; credit_allowed: boolean
    credit_limit: string | null; outstanding: string
  }>
}
