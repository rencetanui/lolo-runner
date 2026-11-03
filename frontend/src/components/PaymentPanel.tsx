import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useProfile } from "@/api/profile"
import { useCheckPayment, usePayments, useStartPayment } from "@/api/payments"
import type { Registration } from "@/api/registrations"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { formatKES } from "@/lib/format"

export function PaymentPanel({ registration }: { registration: Registration }) {
  const qc = useQueryClient()
  const { data: profile } = useProfile()
  const { data: payments } = usePayments(registration.id)
  const start = useStartPayment(registration.id)
  const { mutate: checkPayment, isPending: checking } = useCheckPayment(registration.id)
  const [phone, setPhone] = useState<string | null>(null)

  const latest = payments?.[0]
  const latestId = latest?.id
  const waiting = latest?.status === "pending"
  const phoneValue = phone ?? profile?.phone ?? ""

  // Once paid, refresh the registration so the page flips to "Confirmed".
  useEffect(() => {
    if (latest?.status === "succeeded") qc.invalidateQueries({ queryKey: ["registrations"] })
  }, [latest?.status, qc])

  // If M-Pesa's callback is slow or lost, ask M-Pesa directly every 15 seconds.
  useEffect(() => {
    if (!waiting || !latestId) return
    const timer = window.setInterval(() => checkPayment(latestId), 15_000)
    return () => window.clearInterval(timer)
  }, [waiting, latestId, checkPayment])

  if (waiting && latest) {
    return (
      <Alert>
        <AlertTitle>Check your phone</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>
            We sent an M-Pesa prompt for <strong>{formatKES(latest.amount)}</strong> to {latest.phone}.
            Enter your M-Pesa PIN to finish. This page updates automatically.
          </p>
          <Button variant="outline" size="sm" disabled={checking} onClick={() => checkPayment(latest.id)}>
            {checking ? "Checking…" : "I've paid, check now"}
          </Button>
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-4">
      {latest?.status === "failed" && (
        <Alert variant="destructive">
          <AlertDescription>
            The last attempt didn't go through{latest.result_desc ? `: ${latest.result_desc}` : "."} You can try again.
          </AlertDescription>
        </Alert>
      )}
      {latest?.status === "needs_review" && (
        <Alert variant="destructive">
          <AlertDescription>
            We received a payment we couldn't match automatically. Please contact the organizers
            with your bib number ({registration.bib_number}).
          </AlertDescription>
        </Alert>
      )}

      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          start.mutate(phoneValue.trim() || null)
        }}
      >
        <div className="space-y-2">
          <Label htmlFor="mpesa-phone">M-Pesa phone number</Label>
          <Input
            id="mpesa-phone"
            type="tel"
            inputMode="tel"
            required
            value={phoneValue}
            onChange={(e) => setPhone(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            You'll get a prompt on this number. It can be a different number from your profile.
          </p>
        </div>
        {start.error && (
          <Alert variant="destructive">
            <AlertDescription>{start.error.message}</AlertDescription>
          </Alert>
        )}
        <Button type="submit" disabled={start.isPending}>
          {start.isPending ? "Sending prompt…" : `Pay ${formatKES(registration.fee_amount)} with M-Pesa`}
        </Button>
      </form>
    </div>
  )
}