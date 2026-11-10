import { LegalPage, type LegalSection } from "@/components/LegalPage"

const SECTIONS: LegalSection[] = [
  { heading: "Each event sets its own deadline", body: [
    "Every event page, and the registration page, shows the date until which refunds are available, or says that entries are non-refundable.",
  ] },
  { heading: "If you cancel", body: [
    "If you cancel on or before the event's refund deadline, you get a full refund of your entry fee. After the deadline, or when the event shows no refund deadline, entries are not refundable.",
    "Before you confirm a cancellation, we show you exactly what will happen to your money.",
  ] },
  { heading: "If the organizer cancels the event", body: [
    "Everyone who paid is refunded in full, whatever the event's refund deadline was.",
  ] },
  { heading: "If an event changes", body: [
    "[DECIDE: if the date or location changes, can runners cancel for a full refund? Today the app only refunds under the two rules above.]",
  ] },
  { heading: "How refunds are paid", body: [
    "Refunds are sent by M-Pesa to the phone number the payment came from, for the full amount paid. We don't refund to any other number or method. You'll get an email and SMS with the M-Pesa reference when it's sent.",
    "We aim to send refunds within [X working days] of approving them.",
  ] },
  { heading: "What isn't refunded", body: [
    "[STATE: any transaction fees that aren't returned.] Reservations you never paid for have nothing to refund.",
  ] },
  { heading: "If a payment arrives after your place was released", body: [
    "Your payment will be refunded in full.",
  ] },
  { heading: "Problems", body: [
    "If a refund hasn't arrived when you expect it, contact us through the Help page with your registration details.",
  ] },
]

export default function RefundPolicyPage() {
  return <LegalPage title="Refund Policy" sections={SECTIONS} />
}