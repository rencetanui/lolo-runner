import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import { toApiError } from "./registrations"

export function useDeletionCheck() {
  return useQuery({
    queryKey: ["deletion-check"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/account/deletion-check")
      if (!data) throw new Error("Could not check your account")
      return data
    },
  })
}

export function useRequestDeletion() {
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/account/delete-request")
      if (!data) throw toApiError(error, "Could not start the deletion. Please try again.")
      return data
    },
  })
}

export function useConfirmDeletion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (token: string) => {
      const { data, error } = await api.POST("/api/v1/account/delete-confirm", { body: { token } })
      if (!data) throw toApiError(error, "Could not delete your account. Please try again.")
      return data
    },
    onSuccess: () => {
      qc.setQueryData(["me"], null)
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" })
    },
  })
}

export function useUpdateName() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (full_name: string) => {
      const { data, error } = await api.PATCH("/api/v1/account/name", { body: { full_name } })
      if (!data) throw toApiError(error, "Could not save your name.")
      return data
    },
    onSuccess: (user) => qc.setQueryData(["me"], user),
  })
}

async function downloadMyData() {
  const res = await fetch(`${import.meta.env.VITE_API_URL || ""}/api/v1/account/export`, { credentials: "include" })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw toApiError(body, "Could not download your data.")
  }
  const url = URL.createObjectURL(await res.blob())
  const link = document.createElement("a")
  link.href = url
  link.download = `lolo-runner-my-data-${new Date().toISOString().slice(0, 10)}.json`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function useDownloadMyData() {
  return useMutation({ mutationFn: downloadMyData })
}