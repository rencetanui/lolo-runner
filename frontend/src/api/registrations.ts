import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import type { components } from "./schema"

export type Registration = components["schemas"]["RegistrationOut"]
export type RegistrationInput = components["schemas"]["RegistrationIn"]

export class ApiError extends Error {
  code?: string
  constructor(message: string, code?: string) {
    super(message)
    this.code = code
  }
}

export function toApiError(error: unknown, fallback: string) {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (Array.isArray(detail)) {
    const msg = detail
      .map((d) => String((d as { msg?: string })?.msg ?? "").replace(/^Value error, /, ""))
      .filter(Boolean)
      .join(" · ")
    return new ApiError(msg || fallback)
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    const d = detail as { code?: string; message: string }
    return new ApiError(d.message, d.code)
  }
  return new ApiError(fallback)
}

export function useWaiver() {
  return useQuery({
    queryKey: ["waiver"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/waiver")
      if (!data) throw new Error("Could not load the waiver")
      return data
    },
    staleTime: Infinity,
  })
}

export function useAvailability(eventId: string) {
  return useQuery({
    queryKey: ["availability", eventId],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/events/{event_id}/availability", {
        params: { path: { event_id: eventId } },
      })
      if (!data) throw new Error("Could not load availability")
      return data
    },
    staleTime: 15_000,
  })
}

export function useMyRegistrations() {
  return useQuery({
    queryKey: ["registrations"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/registrations/me")
      if (!data) throw new Error("Could not load your registrations")
      return data
    },
  })
}

export function useRegistration(id: string) {
  return useQuery({
    queryKey: ["registrations", id],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/v1/registrations/{registration_id}", {
        params: { path: { registration_id: id } },
      })
      if (response.status === 404) throw new Error("Registration not found")
      if (!data) throw new Error("Could not load this registration")
      return data
    },
    retry: false,
  })
}

export function useRegister(eventId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: RegistrationInput) => {
      const { data, error } = await api.POST("/api/v1/events/{event_id}/registrations", {
        params: { path: { event_id: eventId } },
        body,
      })
      if (!data) throw toApiError(error, "Could not complete your registration. Please try again.")
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["registrations"] })
      qc.invalidateQueries({ queryKey: ["availability", eventId] })
    },
  })
}

export function useCancelRegistration() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data, error } = await api.DELETE("/api/v1/registrations/{registration_id}", {
        params: { path: { registration_id: id } },
      })
      if (!data) throw toApiError(error, "Could not cancel. Please try again.")
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["registrations"] })
      qc.invalidateQueries({ queryKey: ["availability"] })
    },
  })
}