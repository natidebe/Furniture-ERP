import { Suspense, lazy } from 'react'
import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import type { Role } from './api/types'
import { useAuth } from './auth/AuthContext'
import { Layout } from './components/Layout'
import { Empty, Loading } from './components/ui'
import Login from './pages/Login'

// One chunk per area, so the counter PCs load only what they open.
const Home = lazy(() => import('./pages/Home'))
const Profile = lazy(() => import('./pages/Profile'))
const Search = lazy(() => import('./pages/Search'))
const TransactionHistory = lazy(() => import('./pages/TransactionHistory'))
const Products = lazy(() => import('./pages/products/Products'))
const ProductDetail = lazy(() => import('./pages/products/ProductDetail'))
const ProductForm = lazy(() => import('./pages/products/ProductForm'))
const ImportProducts = lazy(() => import('./pages/products/ImportProducts'))
const StockOverview = lazy(() => import('./pages/stock/StockOverview'))
const Movements = lazy(() => import('./pages/stock/Movements'))
const GoodsReceipts = lazy(() => import('./pages/stock/GoodsReceipts'))
const Adjustments = lazy(() => import('./pages/stock/Adjustments'))
const Transfers = lazy(() => import('./pages/stock/Transfers'))
const TransferDetail = lazy(() => import('./pages/stock/TransferDetail'))
const NewTransfer = lazy(() => import('./pages/stock/NewTransfer'))
const DisplayDamaged = lazy(() => import('./pages/stock/DisplayDamaged'))
const StockRequests = lazy(() => import('./pages/requests/StockRequests'))
const NewStockRequest = lazy(() => import('./pages/requests/NewStockRequest'))
const StockRequestDetail = lazy(() => import('./pages/requests/StockRequestDetail'))
const ReleaseStock = lazy(() => import('./pages/requests/ReleaseStock'))
const NewSale = lazy(() => import('./pages/sales/NewSale'))
const Sales = lazy(() => import('./pages/sales/Sales'))
const SaleDetail = lazy(() => import('./pages/sales/SaleDetail'))
const DeliveryNote = lazy(() => import('./pages/sales/DeliveryNote'))
const PhoneOrders = lazy(() => import('./pages/sales/PhoneOrders'))
const RecordPayment = lazy(() => import('./pages/payments/RecordPayment'))
const Payments = lazy(() => import('./pages/payments/Payments'))
const VerifyPayments = lazy(() => import('./pages/payments/VerifyPayments'))
const PaymentDetail = lazy(() => import('./pages/payments/PaymentDetail'))
const Customers = lazy(() => import('./pages/customers/Customers'))
const CustomerDetail = lazy(() => import('./pages/customers/CustomerDetail'))
const CustomerForm = lazy(() => import('./pages/customers/CustomerForm'))
const Reports = lazy(() => import('./pages/reports/Reports'))
const Users = lazy(() => import('./pages/admin/Users'))
const UserForm = lazy(() => import('./pages/admin/UserForm'))
const Locations = lazy(() => import('./pages/admin/Locations'))
const PaymentAccounts = lazy(() => import('./pages/admin/PaymentAccounts'))
const Settings = lazy(() => import('./pages/admin/Settings'))
const AuditLog = lazy(() => import('./pages/admin/AuditLog'))

const ALL: Role[] = ['salesperson', 'storekeeper', 'accountant', 'admin']
const SALES_STAFF: Role[] = ['salesperson', 'accountant', 'admin']
const STOCK_STAFF: Role[] = ['storekeeper', 'accountant', 'admin']
const OFFICE: Role[] = ['accountant', 'admin']
const ADMIN: Role[] = ['admin']

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Loading text="Signing in…" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <>{children}</>
}

/** Menus follow the role; a page the role can't use says so instead of half-loading. */
function Allow({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { is } = useAuth()
  if (!is(...roles)) {
    return <div className="page"><Empty title="This page isn't part of your work" hint="Use the menu on the left. Ask the admin if you need access." /></div>
  }
  return <>{children}</>
}

const page = (roles: Role[], element: ReactNode) => <Allow roles={roles}>{element}</Allow>

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/delivery-notes/:id" element={<RequireAuth><DeliveryNote /></RequireAuth>} />
        <Route element={<RequireAuth><Layout /></RequireAuth>}>
          <Route index element={<Home />} />
          <Route path="profile" element={<Profile />} />
          <Route path="search" element={<Search />} />
          <Route path="transactions/:number" element={<TransactionHistory />} />

          <Route path="products" element={<Products />} />
          <Route path="products/new" element={page(ADMIN, <ProductForm />)} />
          <Route path="products/import" element={page(ADMIN, <ImportProducts />)} />
          <Route path="products/:id" element={<ProductDetail />} />
          <Route path="products/:id/edit" element={page(ADMIN, <ProductForm />)} />

          <Route path="stock" element={<StockOverview />} />
          <Route path="stock/low" element={<StockOverview lowOnly />} />
          <Route path="movements" element={page(STOCK_STAFF, <Movements />)} />
          <Route path="goods-receipts" element={page(STOCK_STAFF, <GoodsReceipts />)} />
          <Route path="adjustments" element={page(STOCK_STAFF, <Adjustments />)} />
          <Route path="transfers" element={<Transfers />} />
          <Route path="transfers/new" element={page(OFFICE, <NewTransfer />)} />
          <Route path="transfers/:id" element={<TransferDetail />} />
          <Route path="display-damaged" element={<DisplayDamaged />} />

          <Route path="stock-requests" element={<StockRequests />} />
          <Route path="stock-requests/new" element={page(['salesperson', 'admin'], <NewStockRequest />)} />
          <Route path="stock-requests/:id" element={<StockRequestDetail />} />
          <Route path="stock-requests/:id/release" element={page(['storekeeper', 'admin'], <ReleaseStock />)} />

          <Route path="sales/new" element={page(SALES_STAFF, <NewSale />)} />
          <Route path="sales" element={<Sales />} />
          <Route path="sales/:id" element={<SaleDetail />} />
          <Route path="phone-orders" element={<PhoneOrders />} />

          <Route path="payments" element={page(SALES_STAFF, <Payments />)} />
          <Route path="payments/new" element={page(SALES_STAFF, <RecordPayment />)} />
          <Route path="payments/verify" element={page(OFFICE, <VerifyPayments />)} />
          <Route path="payments/:id" element={page(SALES_STAFF, <PaymentDetail />)} />

          <Route path="customers" element={page(SALES_STAFF, <Customers />)} />
          <Route path="customers/new" element={page(SALES_STAFF, <CustomerForm />)} />
          <Route path="customers/:id" element={page(SALES_STAFF, <CustomerDetail />)} />
          <Route path="customers/:id/edit" element={page(SALES_STAFF, <CustomerForm />)} />

          <Route path="reports" element={page(ALL, <Reports />)} />
          <Route path="reports/:name" element={page(ALL, <Reports />)} />
          <Route path="audit" element={page(OFFICE, <AuditLog />)} />

          <Route path="admin/users" element={page(ADMIN, <Users />)} />
          <Route path="admin/users/new" element={page(ADMIN, <UserForm />)} />
          <Route path="admin/users/:id" element={page(ADMIN, <UserForm />)} />
          <Route path="admin/locations" element={page(ALL, <Locations />)} />
          <Route path="admin/payment-accounts" element={page(ALL, <PaymentAccounts />)} />
          <Route path="admin/settings" element={page(ALL, <Settings />)} />

          <Route path="*" element={<div className="page"><Empty title="Page not found" hint="Check the address, or use the menu." /></div>} />
        </Route>
      </Routes>
    </Suspense>
  )
}
