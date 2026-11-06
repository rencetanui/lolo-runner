import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "./client"
import { toApiError } from "./registrations"
import type { components } from "./schema"

type S = components["schemas"]
export type OrganizerEvent = S["EventAdminOut"]
export type OrganizerEventSummary = S["EventSummaryOut"]
export type DistanceAdmin = S["DistanceAdminOut"]
export type EventInput = S["EventIn"]
export type EventChanges = S["EventUpdate"]
export type DistanceInput = S["DistanceIn"]
export type DistanceChanges = S["DistanceUpdate"]

const listKey = ["organizer", "events"] as const
const detailKey = (id: string) => ["organizer", "events", id] as const

function unwrap<T>(result: { data?: T; error?: unknown }, fallback: string): T {
  if (result.data === undefined) throw toApiError(result.error, fallback)
  return result.data
}

// After any change: store the fresh event, refresh the list, and refresh public pages.
function useAfterChange() {
  const qc = useQueryClient()
  return (event: OrganizerEvent) => {
    qc.setQueryData(detailKey(event.id), event)
    qc.invalidateQueries({ queryKey: listKey, exact: true })
    qc.invalidateQueries({ queryKey: ["events"] })
  }
}

export function useOrganizerEvents() {
  return useQuery({
    queryKey: listKey,
    queryFn: async () => unwrap(await api.GET("/api/v1/organizer/events"), "Could not load your events"),
  })
}

export function useOrganizerEvent(id: string) {
  return useQuery({
    queryKey: detailKey(id),
    retry: false,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/organizer/events/{event_id}", { params: { path: { event_id: id } } }),
        "Could not load this event",
      ),
  })
}

export function useCreateEvent() {
  const after = useAfterChange()
  return useMutation({
    mutationFn: async (body: EventInput) =>
      unwrap(await api.POST("/api/v1/organizer/events", { body }), "Could not create the event"),
    onSuccess: after,
  })
}

export function useUpdateEvent(id: string) {
  const after = useAfterChange()
  return useMutation({
    mutationFn: async (body: EventChanges) =>
      unwrap(
        await api.PATCH("/api/v1/organizer/events/{event_id}", { params: { path: { event_id: id } }, body }),
        "Could not save your changes",
      ),
    onSuccess: after,
  })
}

export function useSetPublished(id: string) {
  const after = useAfterChange()
  return useMutation({
    mutationFn: async (publish: boolean) => {
      const params = { path: { event_id: id } }
      return publish
        ? unwrap(await api.POST("/api/v1/organizer/events/{event_id}/publish", { params }), "Could not publish the event")
        : unwrap(await api.POST("/api/v1/organizer/events/{event_id}/unpublish", { params }), "Could not unpublish the event")
    },
    onSuccess: after,
  })
}

export function useDeleteEvent(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE("/api/v1/organizer/events/{event_id}", {
        params: { path: { event_id: id } },
      })
      if (!response.ok) throw toApiError(error, "Could not delete the event")
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: listKey, exact: true })
      qc.invalidateQueries({ queryKey: ["events"] })
    },
  })
}

export function useAddDistance(id: string) {
  const after = useAfterChange()
  return useMutation({
    mutationFn: async (body: DistanceInput) =>
      unwrap(
        await api.POST("/api/v1/organizer/events/{event_id}/distances", { params: { path: { event_id: id } }, body }),
        "Could not add the distance",
      ),
    onSuccess: after,
  })
}

export function useUpdateDistance(id: string) {
  const after = useAfterChange()
  return useMutation({
    mutationFn: async ({ distanceId, changes }: { distanceId: string; changes: DistanceChanges }) =>
      unwrap(
        await api.PATCH("/api/v1/organizer/events/{event_id}/distances/{distance_id}", {
          params: { path: { event_id: id, distance_id: distanceId } },
          body: changes,
        }),
        "Could not save the distance",
      ),
    onSuccess: after,
  })
}

export function useDeleteDistance(id: string) {
  const after = useAfterChange()
  return useMutation({
    mutationFn: async (distanceId: string) =>
      unwrap(
        await api.DELETE("/api/v1/organizer/events/{event_id}/distances/{distance_id}", {
          params: { path: { event_id: id, distance_id: distanceId } },
        }),
        "Could not delete the distance",
      ),
    onSuccess: after,
  })
}

export function useParticipants(id: string, page: number, pageSize: number) {
  return useQuery({
    queryKey: ["organizer", "participants", id, page, pageSize],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/organizer/events/{event_id}/participants", {
          params: { path: { event_id: id }, query: { page, page_size: pageSize } },
        }),
        "Could not load participants",
      ),
    placeholderData: keepPreviousData,
  })
}

export function useCancelPreview(id: string, enabled: boolean) {
  return useQuery({
    queryKey: ["organizer", "cancel-preview", id],
    enabled,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/organizer/events/{event_id}/cancel-preview", { params: { path: { event_id: id } } }),
        "Could not load the cancellation details",
      ),
  })
}

export function useCancelEvent(id: string) {
  const after = useAfterChange()
  return useMutation({
    mutationFn: async (reason: string) =>
      unwrap(
        await api.POST("/api/v1/organizer/events/{event_id}/cancel", {
          params: { path: { event_id: id } },
          body: { reason },
        }),
        "Could not cancel the event",
      ),
    onSuccess: after,
  })
}