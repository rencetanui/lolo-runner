import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import { toApiError } from "./registrations"
import type { components } from "./schema"

export type Payment = components["schemas"]["PaymentOut"]

export function usePayments(registrationId: string) {
  return useQuery({
    queryKey: ["payments", registrationId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/registrations/{registration_id}/payments", {
        params: { path: { registration_id: registrationId } },
      })
      if (!data) throw new Error("Could not load payment status")
      return data
    },
    // Newest payment comes first. While it's pending, keep polling.
    refetchInterval: (query) => (query.state.data?.[0]?.status === "pending" ? 3000 : false),
  })
}

export function useStartPayment(registrationId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (phone: string | null) => {
      const { data, error } = await api.POST("/api/v1/registrations/{registration_id}/payments", {
        params: { path: { registration_id: registrationId } },
        body: { phone },
      })
      if (!data) throw toApiError(error, "Could not start the payment. Please try again.")
      return data
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["payments", registrationId] }),
  })
}

export function useCheckPayment(registrationId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (paymentId: string) => {
      const { data, error } = await api.POST("/api/v1/payments/{payment_id}/check", {
        params: { path: { payment_id: paymentId } },
      })
      if (!data) throw toApiError(error, "Could not check the payment.")
      return data
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["payments", registrationId] })
      qc.invalidateQueries({ queryKey: ["registrations"] })
    },
  })
}