import { useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import {
  useDeleteEvent, useOrganizerEvent, useSetPublished, useUpdateEvent, type OrganizerEvent,
} from "@/api/organizer"
import { DistanceManager } from "@/components/organizer/DistanceManager"
import {
  detailsPayload, EventDetailsFields, detailsError, toDetails, type EventDetails,
} from "@/components/organizer/EventDetailsFields"
import { CancelEventSection } from "@/components/organizer/CancelEventSection"
import { ParticipantsTable } from "@/components/organizer/ParticipantsTable"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { BannerCard } from "@/components/organizer/BannerCard"

function EventEditor({ event }: { event: OrganizerEvent }) {
  const navigate = useNavigate()
  const update = useUpdateEvent(event.id)
  const setPublished = useSetPublished(event.id)
  const del = useDeleteEvent(event.id)
  const [details, setDetails] = useState<EventDetails>(() => toDetails(event))
  const [localError, setLocalError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const published = event.status === "published"
  const dirty = JSON.stringify(details) !== JSON.stringify(toDetails(event))

    if (event.status === "cancelled") {
      return (
        <>
          <header className="space-y-2">
            <h1 className="text-2xl font-bold sm:text-3xl">{event.name}</h1>
            <Badge variant="destructive">Cancelled</Badge>
          </header>
          <Alert variant="destructive">
            <AlertTitle>This event was cancelled</AlertTitle>
            <AlertDescription>{event.cancellation_reason}</AlertDescription>
          </Alert>
        </>
      )
    }

  function onSave(e: React.FormEvent) {
    e.preventDefault()
    const problem = detailsError(details)
    if (problem) return setLocalError(problem)
    setLocalError(null)
    setSaved(false)
    update.mutate(detailsPayload(details), { onSuccess: () => setSaved(true) })
  }

  function onDelete() {
    if (window.confirm("Delete this event permanently?")) {
      del.mutate(undefined, { onSuccess: () => navigate("/organizer") })
    }
  }

  return (
    <>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold sm:text-3xl">{event.name}</h1>
          <div className="flex items-center gap-3">
            <Badge variant={published ? "default" : "secondary"}>{published ? "Published" : "Draft"}</Badge>
            {published && (
              <Link to={`/events/${event.id}`} className="text-sm underline">View public page →</Link>
            )}
          </div>
        </div>
        <Button
          onClick={() => setPublished.mutate(!published)}
          disabled={setPublished.isPending || dirty}
          variant={published ? "outline" : "default"}
        >
          {setPublished.isPending ? "Working…" : published ? "Unpublish" : "Publish event"}
        </Button>
      </header>
      {dirty && <p className="-mt-6 text-xs text-muted-foreground">Save your changes before publishing or unpublishing.</p>}
      {setPublished.error && (
        <Alert variant="destructive"><AlertDescription>{setPublished.error.message}</AlertDescription></Alert>
      )}
      {!published && (
        <Alert><AlertDescription>This event is a draft. Runners can't see it or register until you publish it.</AlertDescription></Alert>
      )}

      <form onSubmit={onSave}>
        <Card>
          <CardHeader><CardTitle>Details</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <EventDetailsFields value={details} onChange={(d) => { setDetails(d); setSaved(false) }} />
            {(localError || update.error) && (
              <Alert variant="destructive"><AlertDescription>{localError ?? update.error?.message}</AlertDescription></Alert>
            )}
            {saved && !dirty && <Alert><AlertDescription>Saved.</AlertDescription></Alert>}
            <Button type="submit" disabled={!dirty || update.isPending}>
              {update.isPending ? "Saving…" : "Save changes"}
            </Button>
          </CardContent>
        </Card>
      </form>

      <BannerCard event={event} />
      <DistanceManager event={event} />
      <ParticipantsTable eventId={event.id} />

      {published && <CancelEventSection event={event} />}

      <section className="space-y-2 border-t pt-6">
        <h2 className="text-lg font-semibold">Delete event</h2>
        <p className="text-sm text-muted-foreground">
          Only possible while nobody has ever registered. Otherwise, unpublish it instead.
        </p>
        {del.error && <Alert variant="destructive"><AlertDescription>{del.error.message}</AlertDescription></Alert>}
        <Button variant="outline" onClick={onDelete} disabled={del.isPending}>Delete event</Button>
      </section>
    </>
  )
}

export default function OrganizerEventPage() {
  const { id = "" } = useParams()
  const { data: event, isLoading, error } = useOrganizerEvent(id)

  return (
    <main className="mx-auto max-w-4xl space-y-8 p-4 sm:p-6">
      <Link to="/organizer" className="text-sm text-muted-foreground hover:underline">← My events</Link>
      {isLoading && <Skeleton className="h-64" />}
      {error && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}
      {event && <EventEditor event={event} />}
    </main>
  )
}