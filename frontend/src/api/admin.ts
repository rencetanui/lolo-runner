import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import { toApiError } from "./registrations"
import type { components } from "./schema"

type S = components["schemas"]
export type AdminPayment = S["AdminPaymentOut"]
export type AdminPaymentDetail = S["AdminPaymentDetail"]
export type PaymentStatus = AdminPayment["status"]
export type PaymentFilters = { status?: PaymentStatus | ""; attention?: boolean; q?: string; page: number }

export const PAGE_SIZE = 25

export function useAdminSummary(enabled = true) {
  return useQuery({
    queryKey: ["admin", "summary"],
    enabled,
    refetchInterval: 60_000,
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/admin/summary")
      if (!data) throw new Error("Could not load the summary")
      return data
    },
  })
}

export function useAdminPayments(f: PaymentFilters) {
  return useQuery({
    queryKey: ["admin", "payments", f],
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/admin/payments", {
        params: {
          query: {
            status: f.status || undefined,
            attention: f.attention || undefined,
            q: f.q || undefined,
            page: f.page,
            page_size: PAGE_SIZE,
          },
        },
      })
      if (!data) throw new Error("Could not load payments")
      return data
    },
  })
}

export function useAdminPayment(id: string) {
  return useQuery({
    queryKey: ["admin", "payment", id],
    retry: false,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/v1/admin/payments/{payment_id}", {
        params: { path: { payment_id: id } },
      })
      if (response.status === 404) throw new Error("Payment not found")
      if (!data) throw new Error("Could not load this payment")
      return data
    },
  })
}

function useRefreshAfter(id: string) {
  const qc = useQueryClient()
  return (payment: AdminPaymentDetail) => {
    qc.setQueryData(["admin", "payment", id], payment)
    qc.invalidateQueries({ queryKey: ["admin", "payments"] })
    qc.invalidateQueries({ queryKey: ["admin", "summary"] })
  }
}

export function useResolvePayment(id: string) {
  const after = useRefreshAfter(id)
  return useMutation({
    mutationFn: async (body: { action: "confirm" | "dismiss"; note: string; mpesa_receipt: string | null }) => {
      const { data, error } = await api.POST("/api/v1/admin/payments/{payment_id}/resolve", {
        params: { path: { payment_id: id } },
        body,
      })
      if (!data) throw toApiError(error, "Could not resolve this payment.")
      return data
    },
    onSuccess: after,
  })
}

export function useRecheckPayment(id: string) {
  const after = useRefreshAfter(id)
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/admin/payments/{payment_id}/check", {
        params: { path: { payment_id: id } },
      })
      if (!data) throw toApiError(error, "Could not check this payment.")
      return data
    },
    onSuccess: after,
  })
}