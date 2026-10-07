// Status chips — one colour per meaning, everywhere (UI_PAGES.md 3.5):
// grey not started · blue in progress · green done · amber needs attention · red stopped.

export type ChipColour = 'grey' | 'blue' | 'green' | 'amber' | 'red'

const COLOURS: Record<string, Record<string, ChipColour>> = {
  request: {
    pending: 'grey', acknowledged: 'blue', partially_released: 'blue', released: 'green',
    closed: 'green', rejected: 'red', cancelled: 'red',
  },
  fulfilment: {
    draft: 'grey', pending: 'grey', confirmed: 'blue', prepared: 'blue',
    partially_released: 'blue', released: 'green', cancelled: 'red', voided: 'red',
  },
  orderPayment: { unpaid: 'grey', partial: 'amber', paid: 'green' },
  payment: { unverified: 'amber', verified: 'green', rejected: 'red', reversed: 'red' },
  transfer: { in_transit: 'blue', received: 'green', short: 'amber', cancelled: 'red' },
  adjustment: { proposed: 'amber', approved: 'green', rejected: 'red' },
  condition: { new: 'grey', display: 'amber', damaged: 'amber' },
  active: { true: 'green', false: 'grey' },
}

export type ChipKind = keyof typeof COLOURS

const LABELS: Record<string, string> = {
  partially_released: 'Partially released',
  in_transit: 'In transit',
  walk_in: 'Walk-in',
  out_of_city: 'Out-of-city',
  official: 'Official receipt',
  none: 'Without receipt',
  phone: 'Phone order',
  customer_pickup: 'Customer pickup',
  branch: 'To branch',
  mobile_money: 'Mobile money',
  sub_store: 'Sub-store',
  transfer_out: 'Transfer out',
  transfer_in: 'Transfer in',
  opening_balance: 'Opening balance',
  true: 'Active',
  false: 'Inactive',
}

export function label(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  if (LABELS[value]) return LABELS[value]
  const s = value.replace(/_/g, ' ')
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export function chipColour(kind: ChipKind, value: string): ChipColour {
  return COLOURS[kind]?.[value] ?? 'grey'
}

export const ROLE_LABEL: Record<string, string> = {
  salesperson: 'Salesperson',
  storekeeper: 'Storekeeper',
  accountant: 'Accountant',
  admin: 'Admin',
}

export const MOVEMENT_TYPES = ['receipt', 'transfer_out', 'transfer_in', 'sale', 'return',
  'adjustment', 'reversal'] as const

export const ADJUSTMENT_REASONS = ['count', 'damage', 'loss', 'found', 'opening_balance'] as const

export const CONDITIONS = ['new', 'display', 'damaged'] as const

export const PAYMENT_METHODS = ['bank', 'cash', 'mobile_money'] as const

export const CUSTOMER_TYPES = ['walk_in', 'reseller', 'out_of_city'] as const
