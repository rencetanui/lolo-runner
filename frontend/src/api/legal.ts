import { useQuery } from "@tanstack/react-query"
import { api } from "./client"

export function useLegalVersion() {
  return useQuery({
    queryKey: ["legal-version"],
    staleTime: Infinity,
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/legal/version")
      return data?.version ?? null
    },
  })
}