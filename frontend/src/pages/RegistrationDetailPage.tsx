import { Link, useNavigate, useParams } from "react-router-dom"
import { useCancelRegistration, useRegistration } from "@/api/registrations"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDate, formatDateTime, formatKES } from "@/lib/format"
import { PaymentPanel } from "@/components/PaymentPanel"

export default function RegistrationDetailPage() {
  const { id = "" } = useParams()
  const navigate = useNavigate()
  const { data: reg, isLoading, error } = useRegistration(id)
  const cancel = useCancelRegistration()

  if (isLoading) return <Skeleton className="m-4 mx-auto h-64 max-w-2xl" />
  if (error || !reg)
    return (
      <main className="mx-auto max-w-2xl p-4">
        <Alert variant="destructive"><AlertDescription>{error?.message ?? "Not found"}</AlertDescription></Alert>
      </main>
    )

  const pending = reg.status === "pending_payment"
  const cancelled = reg.status === "cancelled"

  function onCancel() {
    if (window.confirm("Cancel this registration? Your spot will be released.")) {
      cancel.mutate(reg!.id, { onSuccess: () => navigate("/account") })
    }
  }

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-4 sm:p-6">
      <Link to="/account" className="text-sm text-muted-foreground hover:underline">← My account</Link>

      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <div>
            <CardTitle>{reg.event.name}</CardTitle>
            <p className="text-sm text-muted-foreground">
              {formatDate(reg.event.event_date)} · {reg.event.location}
            </p>
          </div>
          <Badge variant={reg.status === "confirmed" ? "default" : "secondary"}>
            {cancelled ? "Cancelled" : pending ? "Awaiting payment" : "Confirmed"}
          </Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4 text-center">
            <div className="rounded-lg border p-4">
              <div className="text-xs uppercase text-muted-foreground">Bib number</div>
              <div className="text-4xl font-bold">{reg.bib_number}</div>
            </div>
            <div className="rounded-lg border p-4">
              <div className="text-xs uppercase text-muted-foreground">Distance</div>
              <div className="text-4xl font-bold">{reg.distance.name}</div>
            </div>
          </div>

          {reg.status === "confirmed" && (
            <p className="text-sm text-muted-foreground">
              A confirmation is on its way to your email and phone.
            </p>
          )}

          {pending && (
            <>
              <Alert>
                <AlertDescription>
                  Entry fee: <strong>{formatKES(reg.fee_amount)}</strong>.{" "}
                  {reg.expires_at && <>Your spot is held until {formatDateTime(reg.expires_at)}.</>}
                </AlertDescription>
              </Alert>
              <PaymentPanel registration={reg} />
            </>
          )}
          {cancel.error && (
            <Alert variant="destructive"><AlertDescription>{cancel.error.message}</AlertDescription></Alert>
          )}
          {!cancelled && (
            <Button variant="outline" onClick={onCancel} disabled={cancel.isPending}>
              Cancel registration
            </Button>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
