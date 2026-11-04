import { useState } from "react"
import { useParticipants } from "@/api/organizer"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

const PAGE_SIZE = 25

export function ParticipantsTable({ eventId }: { eventId: string }) {
  const [page, setPage] = useState(1)
  const { data, isLoading, error } = useParticipants(eventId, page, PAGE_SIZE)
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Participants{data ? ` (${data.total})` : ""}</h2>
        <a
          href={`/api/v1/organizer/events/${eventId}/participants.csv`}
          download
          className={buttonVariants({ variant: "outline", size: "sm" })}
        >
          Download CSV
        </a>
      </div>
      <p className="text-xs text-muted-foreground">
        Contains personal data. Share it only with people who need it to run the event.
      </p>

      {error && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}
      {isLoading && <Skeleton className="h-32" />}
      {data?.total === 0 && <p className="text-sm text-muted-foreground">No registrations yet.</p>}

      {!!data?.items.length && (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
              <tr>
                {["Bib", "Name", "Distance", "Category", "Phone", "Status"].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((p) => (
                <tr key={p.registration_id} className="border-t">
                  <td className="px-3 py-2 font-medium">{p.bib_number}</td>
                  <td className="px-3 py-2">{p.full_name}</td>
                  <td className="px-3 py-2">{p.distance_name}</td>
                  <td className="px-3 py-2">{p.age_category ?? "—"}</td>
                  <td className="px-3 py-2">{p.phone ?? "—"}</td>
                  <td className="px-3 py-2">
                    <Badge variant={p.status === "confirmed" ? "default" : "secondary"}>
                      {p.status === "confirmed" ? "Confirmed" : "Awaiting payment"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
          <span className="text-muted-foreground">Page {page} of {pages}</span>
          <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button>
        </div>
      )}
    </section>
  )
}