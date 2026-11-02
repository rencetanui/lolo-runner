import { useQuery } from "@tanstack/react-query"
import { api } from "./client"

export function useEvents(upcomingOnly = true) {
  return useQuery({
    queryKey: ["events", { upcomingOnly }],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/events", {
        params: { query: { upcoming_only: upcomingOnly } },
      })
      if (error) throw new Error("Could not load events")
      return data
    },
  })
}

export function useEvent(id: string) {
  return useQuery({
    queryKey: ["events", id],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/v1/events/{event_id}", {
        params: { path: { event_id: id } },
      })
      if (response.status === 404) throw new Error("Event not found")
      if (!data) throw new Error("Could not load event")
      return data
    },
    retry: false,
  })
}