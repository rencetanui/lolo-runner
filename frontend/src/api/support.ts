import { useMutation } from "@tanstack/react-query"
import { api } from "./client"
import { toApiError } from "./registrations"
import type { components } from "./schema"

export type SupportInput = components["schemas"]["SupportIn"]

export function useSendSupport() {
  return useMutation({
    mutationFn: async (body: SupportInput) => {
      const { data, error } = await api.POST("/api/v1/support", { body })
      if (!data) throw toApiError(error, "Could not send your message. Please try again.")
      return data
    },
  })
}