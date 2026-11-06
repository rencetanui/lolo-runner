import { useState } from "react"
import { Link } from "react-router-dom"
import { PAGE_SIZE, useAdminRefunds, type RefundStatus } from "@/api/admin"
import { AdminNav } from "@/components/admin/AdminNav"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime, formatKES } from "@/lib/format"

export const REASON_LABEL: Record<string, string> = {
  runner_cancelled: "Runner cancelled",
  event_cancelled: "Event cancelled",
  late_payment: "Late payment",
  admin: "Admin",
}

export function RefundStatusBadge({ status }: { status: RefundStatus }) {
  const variant = status === "paid" ? "default" : status === "requested" ? "destructive" : "secondary"
  const label = status === "paid" ? "Sent" : status === "requested" ? "To send" : "Rejected"
  return <Badge variant={variant}>{label}</Badge>
}

export default function AdminRefundsPage() {
  const [status, setStatus] = useState<RefundStatus | "">("requested")
  const [search, setSearch] = useState("")
  const [q, setQ] = useState("")
  const [page, setPage] = useState(1)
  const { data, isLoading, error } = useAdminRefunds({ status, q, page })
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
      <h1 className="text-2xl font-bold sm:text-3xl">Refunds</h1>
      <AdminNav />

      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(e) => { e.preventDefault(); setQ(search.trim()); setPage(1) }}
      >
        <select
          aria-label="Status"
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={status}
          onChange={(e) => { setStatus(e.target.value as RefundStatus | ""); setPage(1) }}
        >
          <option value="requested">To send</option>
          <option value="paid">Sent</option>
          <option value="rejected">Rejected</option>
          <option value="">All</option>
        </select>
        <Input className="w-72" placeholder="Name, email, phone or M-Pesa code" value={search}
          onChange={(e) => setSearch(e.target.value)} />
        <Button type="submit" size="sm">Search</Button>
      </form>

      {error && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}
      {isLoading && <Skeleton className="h-48" />}
      {data?.total === 0 && <p className="text-sm text-muted-foreground">Nothing here.</p>}

      {!!data?.items.length && (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
              <tr>{["Requested", "Runner", "Event", "Amount", "Send to", "Why", "Status", ""].map((h) => (
                <th key={h} className="px-3 py-2 font-medium">{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {data.items.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="whitespace-nowrap px-3 py-2">{formatDateTime(r.created_at)}</td>
                  <td className="px-3 py-2">{r.user.full_name}<div className="text-xs text-muted-foreground">{r.user.email}</div></td>
                  <td className="px-3 py-2">{r.event.name}<div className="text-xs text-muted-foreground">{r.distance_name} · bib {r.bib_number}</div></td>
                  <td className="px-3 py-2 font-medium">{formatKES(r.amount)}</td>
                  <td className="px-3 py-2">{r.phone}</td>
                  <td className="px-3 py-2">{REASON_LABEL[r.reason]}</td>
                  <td className="px-3 py-2"><RefundStatusBadge status={r.status} /></td>
                  <td className="px-3 py-2"><Link to={`/admin/refunds/${r.id}`} className="underline">Open</Link></td>
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
    </main>
  )
}