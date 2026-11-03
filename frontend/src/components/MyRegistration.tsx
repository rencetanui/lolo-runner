import { Link } from "react-router-dom"
import { useMyRegistrations } from "@/api/registrations"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDate } from "@/lib/format"

export function MyRegistrations() {
  const { data, isLoading } = useMyRegistrations()

  return (
    <Card>
      <CardHeader>
        <CardTitle>My races</CardTitle>
        <CardDescription>Your upcoming and pending registrations.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <Skeleton className="h-16" />}
        {data?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Nothing yet. <Link to="/" className="underline">Find a race →</Link>
          </p>
        )}
        {data?.map((r) => (
          <Link key={r.id} to={`/registrations/${r.id}`}
            className="flex items-center justify-between rounded-md border p-3 hover:bg-muted/50">
            <div>
              <div className="font-medium">{r.event.name} · {r.distance.name}</div>
              <div className="text-sm text-muted-foreground">
                {formatDate(r.event.event_date)} · Bib {r.bib_number}
              </div>
            </div>
            <Badge variant={r.status === "confirmed" ? "default" : "secondary"}>
              {r.status === "confirmed" ? "Confirmed" : "Awaiting payment"}
            </Badge>
          </Link>
        ))}
      </CardContent>
    </Card>
  )
}