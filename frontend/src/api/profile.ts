import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { components } from "./schema"

export type Profile = components["schemas"]["RunnerProfileOut"]
export type ProfileInput = components["schemas"]["RunnerProfileIn"]

export function useProfile() {
  return useQuery({
    queryKey: ["profile"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/v1/runners/me")
      if (response.status === 404) return null          // no profile yet is normal
      if (!data) throw new Error("Could not load your profile")
      return data
    },
    retry: false,
  })
}

export function useSaveProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: ProfileInput) => {
      const { data, error, response } = await api.PUT("/api/v1/runners/me", { body })
      if (response.status === 422) {
        const detail = (error as { detail?: { loc: (string | number)[]; msg: string }[] } | undefined)?.detail
        const messages = detail?.map((d) => d.msg.replace(/^Value error, /, ""))
        throw new Error(messages?.join(" · ") || "Please check your details")
      }
      if (!data) throw new Error("Could not save your profile. Please try again.")
      return data
    },
    onSuccess: (profile) => qc.setQueryData(["profile"], profile),
  })
}