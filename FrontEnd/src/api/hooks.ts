import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, errorMessage } from './client'
import type { Params } from './client'
import type {
  Category, Location, Paginated, PaymentAccount, PermissionInfo, SystemSettings, Unit,
} from './types'
import { useToast } from '../components/Toast'

/** GET a path; the query key is the path plus its params, so lists refetch on filter change. */
export function useApi<T>(path: string | null, params?: Params, options?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: [path, params ?? {}],
    queryFn: () => api.get<T>(path as string, params),
    enabled: path !== null,
    placeholderData: keepPreviousData,
    refetchInterval: options?.refetchInterval,
  })
}

/** Reference data that rarely changes: loaded once per session. */
function useReference<T>(path: string) {
  return useQuery({
    queryKey: [path, 'reference'],
    queryFn: async () => {
      const data = await api.get<Paginated<T> | T[]>(path, { page_size: 200 })
      return Array.isArray(data) ? data : data.results
    },
    staleTime: 5 * 60_000,
  })
}

export const useLocations = () => useReference<Location>('/locations/')
export const usePaymentAccounts = () => useReference<PaymentAccount>('/payment-accounts/')
export const useCategories = () => useReference<Category>('/categories/')
export const useUnits = () => useReference<Unit>('/units/')
export const usePermissions = () => useReference<PermissionInfo>('/permissions/')

export function useSettings() {
  return useQuery({
    queryKey: ['/settings/'],
    queryFn: () => api.get<SystemSettings>('/settings/'),
    staleTime: 60_000,
  })
}

/** Locations that hold stock and appear on screens (In Transit is a system location). */
export function useRealLocations() {
  const q = useLocations()
  return { ...q, data: q.data?.filter((l) => l.code !== 'TRANSIT') }
}

export function locationCode(locations: Location[] | undefined, id: number | null | undefined) {
  return locations?.find((l) => l.id === id)?.code ?? '—'
}

interface ActionOptions<TResult> {
  /** Toast shown after success. */
  success?: string | ((result: TResult) => string)
  onSuccess?: (result: TResult) => void
  /** Show errors as a toast (default). Forms set false and show the error inline. */
  toastErrors?: boolean
}

/**
 * A POST/PATCH that changes data. Every query is refetched afterwards: stock, money and
 * statuses are linked (a release changes the request, the sale, the stock and the dashboard),
 * so refreshing everything is the simple, correct choice for an app of this size.
 */
export function useAction<TBody = unknown, TResult = unknown>(
  fn: (body: TBody) => Promise<TResult>,
  options: ActionOptions<TResult> = {},
) {
  const queryClient = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: fn,
    onSuccess: async (result) => {
      await queryClient.invalidateQueries()
      if (options.success) {
        toast.show(typeof options.success === 'function' ? options.success(result) : options.success)
      }
      options.onSuccess?.(result)
    },
    onError: (error) => {
      if (options.toastErrors !== false) toast.show(errorMessage(error), 'error')
    },
  })
}
