import { useQuery } from "@tanstack/react-query"
import { api } from "./client"
import type { components } from "./schema"

export type CancellationPreview = components["schemas"]["CancellationPreviewOut"]
export type MyRefund = components["schemas"]["RefundOut"]

export function useCancellationPreview(registrationId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["cancellation-preview", registrationId],
    enabled,
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/registrations/{registration_id}/cancellation-preview", {
        params: { path: { registration_id: registrationId } },
      })
      if (!data) throw new Error("Could not load the refund details")
      return data
    },
  })
}

export function useMyRefund(registrationId: string) {
  return useQuery({
    queryKey: ["my-refund", registrationId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/registrations/{registration_id}/refund", {
        params: { path: { registration_id: registrationId } },
      })
      return data ?? null
    },
  })
}