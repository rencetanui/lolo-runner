import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import { toApiError } from "./registrations"

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
      const { data, error, response } = await api.POST("/api/v1/auth/login", { body })
      if (response.status === 401) throw new Error("Incorrect email or password")
      if (response.status === 429) throw toApiError(error, "Too many attempts. Please try again later.")
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
      const { data, error, response } = await api.POST("/api/v1/auth/signup", { body })
      if (response.status === 409) throw new Error("An account with this email already exists")
      if (response.status === 429) throw toApiError(error, "Too many attempts. Please try again later.")
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

export function useVerifyEmail() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (token: string) => {
      const { data, error } = await api.POST("/api/v1/auth/verify-email", { body: { token } })
      if (!data) throw toApiError(error, "Could not verify your email. Please try again.")
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  })
}

export function useResendVerification() {
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/auth/resend-verification")
      if (!data) throw toApiError(error, "Could not send the email. Please try again.")
      return data
    },
  })
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: async (email: string) => {
      const { data, error } = await api.POST("/api/v1/auth/forgot-password", { body: { email } })
      if (!data) throw toApiError(error, "Could not send the reset link. Please try again.")
      return data
    },
  })
}

export function useResetPassword() {
  return useMutation({
    mutationFn: async (body: { token: string; new_password: string }) => {
      const { data, error } = await api.POST("/api/v1/auth/reset-password", { body })
      if (!data) throw toApiError(error, "Could not reset your password. Please try again.")
      return data
    },
  })
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (body: { current_password: string; new_password: string }) => {
      const { data, error } = await api.POST("/api/v1/auth/change-password", { body })
      if (!data) throw toApiError(error, "Could not change your password. Please try again.")
      return data
    },
  })
}

export function useGoogleConfig() {
  return useQuery({
    queryKey: ["google-config"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/auth/google/config")
      return data ?? { enabled: false, client_id: null }
    },
    staleTime: Infinity,
  })
}

export function useGoogleLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (credential: string) => {
      const { data, error } = await api.POST("/api/v1/auth/google", { body: { credential } })
      if (!data) throw toApiError(error, "Could not sign in with Google. Please try again.")
      return data
    },
    onSuccess: (user) => qc.setQueryData(["me"], user),
  })
}
