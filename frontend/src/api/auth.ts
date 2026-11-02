import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/v1/auth/me")
      if (response.status === 401) return null
      if (!data) throw new Error("Could not load your session")
      return data
    },
    staleTime: 5 * 60_000,
    retry: false,
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { email: string; password: string }) => {
      const { data, response } = await api.POST("/api/v1/auth/login", { body })
      if (response.status === 401) throw new Error("Incorrect email or password")
      if (!data) throw new Error("Could not sign in. Please try again.")
      return data
    },
    onSuccess: (user) => qc.setQueryData(["me"], user),
  })
}

export function useSignup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { full_name: string; email: string; password: string }) => {
      const { data, response } = await api.POST("/api/v1/auth/signup", { body })
      if (response.status === 409) throw new Error("An account with this email already exists")
      if (response.status === 422) throw new Error("Please check your details and try again")
      if (!data) throw new Error("Could not create your account. Please try again.")
      return data
    },
    onSuccess: (user) => qc.setQueryData(["me"], user),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/auth/logout")
    },
    onSuccess: () => qc.setQueryData(["me"], null),
  })
}