import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { PAGE_SIZE, useAdminPayments, useAdminSummary, type PaymentFilters, type PaymentStatus } from "@/api/admin"
import { PaymentStatusBadge } from "@/components/admin/PaymentStatusBadge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime, formatKES } from "@/lib/format"
import { AdminNav } from "@/components/admin/AdminNav"

function Tile({ label, value, alert, onClick }: { label: string; value: number; alert?: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className="rounded-lg border p-4 text-left transition hover:bg-muted/50">
      <div className={`text-3xl font-bold ${alert && value > 0 ? "text-destructive" : ""}`}>{value}</div>
      <div className="text-sm text-muted-foreground">{label}</div>
    </button>
  )
}

export default function AdminPaymentsPage() {
  const [filters, setFilters] = useState<PaymentFilters>({ page: 1 })
  const [search, setSearch] = useState("")
  const [range, setRange] = useState({ start: "", end: "" })
  const summary = useAdminSummary()
  const navigate = useNavigate()
  const { data, isLoading, error } = useAdminPayments(filters)
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))
  const show = (next: Partial<PaymentFilters>) => setFilters({ page: 1, ...next })

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
      <h1 className="text-2xl font-bold sm:text-3xl">Payments</h1>
      <AdminNav />
      {summary.data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Tile label="Need review" value={summary.data.needs_review} alert onClick={() => show({ status: "needs_review" })} />
          <Tile label="Need a refund" value={summary.data.needs_refund} alert onClick={() => show({ attention: true })} />
          <Tile label="Stuck pending (10+ min)" value={summary.data.stuck_pending} alert onClick={() => show({ attention: true })} />
          <Tile label="Failed in 24 hours" value={summary.data.failed_24h} onClick={() => show({ status: "failed" })} />
        </div>
      )}

      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          setFilters((f) => ({ ...f, q: search.trim(), page: 1 }))
        }}
      >
        <select
          aria-label="Status"
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={filters.status ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value as PaymentStatus | "", page: 1 }))}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="succeeded">Paid</option>
          <option value="failed">Failed</option>
          <option value="needs_review">Needs review</option>
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={!!filters.attention}
            onChange={(e) => setFilters((f) => ({ ...f, attention: e.target.checked, page: 1 }))}
          />
          Needs attention
        </label>
        <Input className="w-72" placeholder="Name, email, phone, receipt or bib" value={search}
          onChange={(e) => setSearch(e.target.value)} />
        <Button type="submit" size="sm">Search</Button>
        <Button type="button" size="sm" variant="outline"
          onClick={() => { setSearch(""); setFilters({ page: 1 }) }}>Clear</Button>
      </form>

      {error && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}
      {isLoading && <Skeleton className="h-48" />}
      {data?.total === 0 && <p className="text-sm text-muted-foreground">No payments match.</p>}

      {!!data?.items.length && (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
              <tr>{["When", "Runner", "Event", "Amount", "Status", "Receipt", ""].map((h) => (
                <th key={h} className="px-3 py-2 font-medium">{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {data.items.map((p) => (
                <tr key={p.id} className="border-t">
                  <td className="whitespace-nowrap px-3 py-2">{formatDateTime(p.created_at)}</td>
                  <td className="px-3 py-2">{p.user.full_name}<div className="text-xs text-muted-foreground">{p.phone}</div></td>
                  <td className="px-3 py-2">{p.event.name}<div className="text-xs text-muted-foreground">{p.distance_name} · bib {p.bib_number}</div></td>
                  <td className="px-3 py-2">{formatKES(p.amount)}</td>
                  <td className="px-3 py-2">
                    <PaymentStatusBadge status={p.status} />
                    {p.needs_refund && <div className="mt-1 text-xs text-destructive">Needs refund</div>}
                  </td>
                  <td className="px-3 py-2">{p.mpesa_receipt ?? "—"}</td>
                  <td className="px-3 py-2"><Link to={`/admin/payments/${p.id}`} className="underline">Open</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <Button size="sm" variant="outline" disabled={filters.page <= 1}
            onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}>Previous</Button>
          <span className="text-muted-foreground">Page {filters.page} of {pages}</span>
          <Button size="sm" variant="outline" disabled={filters.page >= pages}
            onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}>Next</Button>
        </div>
      )}

      <section className="space-y-2 border-t pt-6">
        <h2 className="text-lg font-semibold">Reconciliation export</h2>
        <p className="text-sm text-muted-foreground">
          Every payment created between two dates (Nairobi time), to match against the M-Pesa statement.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Input type="date" className="w-44" value={range.start} onChange={(e) => setRange((r) => ({ ...r, start: e.target.value }))} />
          <span className="text-sm text-muted-foreground">to</span>
          <Input type="date" className="w-44" value={range.end} onChange={(e) => setRange((r) => ({ ...r, end: e.target.value }))} />
          {range.start && range.end ? (
            <a download className={buttonVariants({ variant: "outline", size: "sm" })}
              href={`/api/v1/admin/payments.csv?start=${range.start}&end=${range.end}`}>Download CSV</a>
          ) : (
            <Button size="sm" variant="outline" disabled>Download CSV</Button>
          )}
        </div>
      </section>
    </main>
  )
}
