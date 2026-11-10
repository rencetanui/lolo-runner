import { LegalPage, type LegalSection } from "@/components/LegalPage"

const SECTIONS: LegalSection[] = [
  { heading: "Who we are", body: [
    "[COMPANY NAME, registered office and registration number] (\"we\", \"Lolo Runner\") runs this website and app, a booking platform for running events in Kenya. By creating an account or registering for an event you agree to these Terms.",
  ] },
  { heading: "Your account", body: [
    "Give accurate details and keep your password private. Tell us straight away if you think someone else is using your account.",
    "Runners under 18 may take part only with a parent or guardian's consent, given when registering. [LAWYER: confirm how accounts and consent for minors should work.]",
  ] },
  { heading: "Events and organizers", body: [
    "Each event is run by its organizer, not by us. We provide the booking and payment tools. Dates, venues, start times, routes and rules are set by the organizer and can change.",
    "If the date, location or start time of an event you registered for changes, we will tell you by email and SMS.",
  ] },
  { heading: "Registering", body: [
    "Your entry is personal to you and can't be transferred. [DECIDE: transfers and distance changes.] You must meet the age and other requirements of the distance you choose.",
    "While you pay, we hold your place for [30] minutes. If payment isn't completed in that time, the place is released.",
  ] },
  { heading: "Payments", body: [
    "Entry fees are in Kenya shillings and are paid by M-Pesa. We show the exact amount before you pay. Your registration is confirmed only when M-Pesa confirms your payment. [STATE who pays transaction fees, if any.]",
    "Do not request a payment prompt on a phone number that isn't yours or that you have no permission to use.",
  ] },
  { heading: "Cancellations and refunds", body: [
    "See our Refund Policy. In short: refunds depend on each event's refund deadline, and every paid entry is refunded in full if the organizer cancels the event.",
  ] },
  { heading: "Health and safety", body: [
    "Running involves risk. You confirm that you are fit to take part and you accept the waiver shown when you register. Keep your emergency contact and medical information accurate.",
  ] },
  { heading: "Acceptable use", body: [
    "Don't give false information, try to disrupt or break into the service, scrape it, or use it to harass anyone. We may suspend accounts that do.",
  ] },
  { heading: "Closing your account", body: [
    "You can delete your account from your account page. Deletion is blocked while you hold upcoming entries or while money is owed to or by you, so that nobody loses money. We may suspend or close accounts that break these Terms.",
  ] },
  { heading: "Our responsibility", body: [
    "[LAWYER: limitation of liability and consumer-law wording for Kenya.] Nothing in these Terms limits rights you have under Kenyan law that can't be limited.",
  ] },
  { heading: "Changes to these Terms", body: [
    "We may update these Terms. When a change matters, we'll ask you to accept the new version before your next registration.",
  ] },
  { heading: "Law and contact", body: [
    "These Terms are governed by the laws of Kenya. [LAWYER: confirm.] Contact us at [SUPPORT EMAIL] or through the Help page.",
  ] },
]

export default function TermsPage() {
  return <LegalPage title="Terms of Service" sections={SECTIONS} />
}