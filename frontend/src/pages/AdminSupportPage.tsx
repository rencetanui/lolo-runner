import { useState } from "react"
import { PAGE_SIZE, useAdminSupport, useResolveSupport, type AdminSupport, type SupportStatus } from "@/api/admin"
import { AdminNav } from "@/components/admin/AdminNav"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime } from "@/lib/format"

function MessageCard({ m }: { m: AdminSupport }) {
  const resolve = useResolveSupport()
  const [note, setNote] = useState("")
  const open = m.status === "open"
  const subject = encodeURIComponent(`Re: Lolo Runner support ${m.reference}`)
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="text-base">{m.name}</CardTitle>
          <p className="text-sm text-muted-foreground">{m.email} · {formatDateTime(m.created_at)} · ref {m.reference}</p>
        </div>
        <div className="flex gap-2">
          <Badge variant="secondary">{m.topic}</Badge>
          <Badge variant={open ? "destructive" : "default"}>{open ? "Open" : "Resolved"}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="whitespace-pre-line text-sm">{m.message}</p>
        {!open && (
          <p className="text-xs text-muted-foreground">
            Resolved {m.resolved_at && formatDateTime(m.resolved_at)} by {m.resolved_by_name ?? "system"}
            {m.admin_note && ` · ${m.admin_note}`}
          </p>
        )}
        {open && (
          <div className="flex flex-wrap items-center gap-2">
            <a className={buttonVariants({ variant: "outline", size: "sm" })} href={`mailto:${m.email}?subject=${subject}`}>
              Reply by email
            </a>
            <Input className="w-64" placeholder="Note (optional)" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
            <Button size="sm" disabled={resolve.isPending} onClick={() => resolve.mutate({ id: m.id, note: note.trim() || null })}>
              {resolve.isPending ? "Saving…" : "Mark resolved"}
            </Button>
          </div>
        )}
        {resolve.error && <Alert variant="destructive"><AlertDescription>{resolve.error.message}</AlertDescription></Alert>}
      </CardContent>
    </Card>
  )
}

export default function AdminSupportPage() {
  const [status, setStatus] = useState<SupportStatus | "">("open")
  const [page, setPage] = useState(1)
  const { data, isLoading, error } = useAdminSupport({ status, page })
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <h1 className="text-2xl font-bold sm:text-3xl">Support</h1>
      <AdminNav />
      <select
        aria-label="Status"
        className="h-9 rounded-md border bg-background px-2 text-sm"
        value={status}
        onChange={(e) => { setStatus(e.target.value as SupportStatus | ""); setPage(1) }}
      >
        <option value="open">Open</option>
        <option value="resolved">Resolved</option>
        <option value="">All</option>
      </select>

      {error && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}
      {isLoading && <Skeleton className="h-40" />}
      {data?.total === 0 && <p className="text-sm text-muted-foreground">Nothing here.</p>}
      <div className="space-y-3">{data?.items.map((m) => <MessageCard key={m.id} m={m} />)}</div>

      {pages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
          <span className="text-muted-foreground">Page {page} of {pages}</span>
          <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button>
        </div>
      )}
    </main>
  )
}