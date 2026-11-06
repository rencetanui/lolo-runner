import { Link } from "react-router-dom"
import { useOrganizerEvents } from "@/api/organizer"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDate } from "@/lib/format"

export default function OrganizerEventsPage() {
  const { data, isLoading, error } = useOrganizerEvents()

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold sm:text-3xl">My events</h1>
        <Link to="/organizer/events/new" className={buttonVariants()}>New event</Link>
      </div>

      {error && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}
      {isLoading && <Skeleton className="h-24" />}
      {data?.length === 0 && <p className="text-muted-foreground">No events yet. Create your first one.</p>}

      <div className="space-y-3">
        {data?.map((e) => (
          <Link key={e.id} to={`/organizer/events/${e.id}`} className="block">
            <Card className="transition hover:shadow-md">
              <CardHeader className="flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle>{e.name}</CardTitle>
                  <p className="text-sm text-muted-foreground">{formatDate(e.event_date)} · {e.location}</p>
                </div>
                <Badge variant={e.status === "published" ? "default" : e.status === "cancelled" ? "destructive" : "secondary"}>
                  {e.status === "published" ? "Published" : e.status === "cancelled" ? "Cancelled" : "Draft"}
                </Badge>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {e.confirmed} confirmed · {e.held} awaiting payment · {e.capacity} spots in total
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </main>
  )
}