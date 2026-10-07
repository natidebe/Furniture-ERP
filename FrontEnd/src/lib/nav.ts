// The sidebar per role (UI_PAGES.md section 4, design board "Sidebar"). Sections and order
// follow the design; the API still checks every request.
import type { Role } from '../api/types'

export interface NavItem { label: string; to: string; badge?: 'requests' | 'verify' | 'adjustments' | 'arriving' }
export interface NavSection { label: string; items: NavItem[] }

const I = {
  home: { label: 'Home', to: '/' },
  newSale: { label: 'New sale', to: '/sales/new' },
  sales: { label: 'Sales', to: '/sales' },
  phone: { label: 'Phone orders', to: '/phone-orders' },
  payments: { label: 'Payments', to: '/payments' },
  verify: { label: 'Payments to verify', to: '/payments/verify', badge: 'verify' },
  customers: { label: 'Customers & credit', to: '/customers' },
  products: { label: 'Products', to: '/products' },
  stock: { label: 'Stock', to: '/stock' },
  displayDamaged: { label: 'Display & damaged', to: '/display-damaged' },
  requests: { label: 'Stock requests', to: '/stock-requests', badge: 'requests' },
  transfers: { label: 'Transfers', to: '/transfers', badge: 'arriving' },
  receipts: { label: 'Goods receipts', to: '/goods-receipts' },
  adjustments: { label: 'Stock adjustments', to: '/adjustments', badge: 'adjustments' },
  movements: { label: 'Stock movements', to: '/movements' },
  reports: { label: 'Reports', to: '/reports' },
  audit: { label: 'Audit log', to: '/audit' },
  users: { label: 'Users & permissions', to: '/admin/users' },
  locations: { label: 'Locations', to: '/admin/locations' },
  accounts: { label: 'Payment accounts', to: '/admin/payment-accounts' },
  settings: { label: 'Settings', to: '/admin/settings' },
  profile: { label: 'My profile', to: '/profile' },
} satisfies Record<string, NavItem>

const money = [I.home, I.newSale, I.sales, I.phone, I.payments, I.verify, I.customers]
const stock = [I.products, I.stock, I.displayDamaged, I.requests, I.transfers, I.receipts, I.adjustments, I.movements]

export const MENUS: Record<Role, NavSection[]> = {
  salesperson: [
    { label: 'Sell', items: [I.home, I.newSale, I.sales, I.phone, I.payments, I.customers] },
    { label: 'Stock', items: [I.stock, I.products, I.displayDamaged, I.requests, I.transfers] },
    { label: 'You', items: [I.reports, I.profile] },
  ],
  storekeeper: [
    { label: 'Work', items: [I.home, I.requests, I.phone, I.sales, I.transfers, I.receipts] },
    { label: 'Stock', items: [I.stock, I.displayDamaged, I.adjustments, I.movements, I.products] },
    { label: 'You', items: [I.reports, I.profile] },
  ],
  accountant: [
    { label: 'Money', items: money },
    { label: 'Stock', items: stock },
    { label: 'Records', items: [I.reports, I.audit, I.profile] },
  ],
  admin: [
    { label: 'Money', items: money },
    { label: 'Stock', items: stock },
    { label: 'Records', items: [I.reports, I.audit] },
    { label: 'Admin', items: [I.users, I.locations, I.accounts, I.settings] },
    { label: 'You', items: [I.profile] },
  ],
}
