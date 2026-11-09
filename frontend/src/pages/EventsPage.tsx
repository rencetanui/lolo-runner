import { Link } from "react-router-dom"
import { useEvents } from "@/api/events"
import { RegistrationBadge } from "@/components/RegistrationBadge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDate } from "@/lib/format"

export default function EventsPage() {
  const { data, isLoading, error } = useEvents()

  return (
    <main className="mx-auto max-w-5xl p-4 sm:p-6">
      <h1 className="text-2xl font-bold sm:text-3xl">Upcoming races</h1>
      <p className="mb-6 text-muted-foreground">Find your next start line.</p>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading &&
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40" />)}

        {data?.map((event) => (
          <Link key={event.id} to={`/events/${event.id}`}>
            <Card className="h-full transition hover:shadow-md">
              {event.banner_url && (
                <img 
                  src={event.banner_url} 
                  alt="" 
                  loading="lazy" 
                  className="h-36 w-full rounded-t-lg object-cover" 
                />
              )}
              <CardHeader>
                <CardTitle>{event.name}</CardTitle>
                <CardDescription>
                  {formatDate(event.event_date)} · {event.location}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <RegistrationBadge
                  opens={event.registration_opens}
                  closes={event.registration_closes}
                />
                <div className="flex flex-wrap gap-1 text-sm text-muted-foreground">
                  {event.distances.map((d) => (
                    <span key={d.id} className="rounded bg-muted px-2 py-0.5">{d.name}</span>
                  ))}
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}

        {data?.length === 0 && (
          <p className="text-muted-foreground">No upcoming races yet. Check back soon.</p>
        )}
      </div>
    </main>
  )
}
