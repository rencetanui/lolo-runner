import { LegalPage, type LegalSection } from "@/components/LegalPage"

const SECTIONS: LegalSection[] = [
  { heading: "Who is responsible for your data", body: [
    "[COMPANY NAME, address, registration number] is the data controller. Contact: [PRIVACY CONTACT EMAIL]. [ODPC registration number, if registered.]",
  ] },
  { heading: "What we collect", body: [
    "Account: your name, email address and a one-way hash of your password. If you sign in with Google, your Google account ID and email.",
    "Runner profile: date of birth, gender, phone number, county, club, T-shirt size, emergency contact (name, phone, relationship) and, if you choose to add it, medical information.",
    "Registrations: the events and distances you enter, your bib number, the waiver version you accepted and when, guardian consent for under-18s, and an estimated finish time if you give one.",
    "Payments: the amount, the M-Pesa number used, the status and the M-Pesa receipt number. We never see your M-Pesa PIN.",
    "Messages: the emails and SMS we send you, and any messages you send us through the Help page.",
    "Technical: your IP address, used to protect against abuse. It is kept in hashed form for rate limiting and appears in short-lived security logs. [CONFIRM log retention.]",
  ] },
  { heading: "Why we use it", body: [
    "To run your account, register you for events, take payment and send refunds, contact you about your entries, keep the service secure, and meet legal and accounting obligations. [LAWYER: state the legal basis for each purpose.]",
    "We do not sell your data and we do not send marketing messages.",
  ] },
  { heading: "Who can see it", body: [
    "Organizers of an event you register for can see your name, email, phone number, age category, club, T-shirt size, bib number and registration status. They cannot see your payment details, emergency contact or medical information through their normal tools.",
    "Your emergency contact and medical information are used only to help you in an emergency during an event you registered for. [CONFIRM the race-day access process.]",
    "Our staff see the account and payment details needed to help you. Other runners never see your data.",
  ] },
  { heading: "Companies that handle data for us", body: [
    "Safaricom (M-Pesa payments), Africa's Talking (SMS), [EMAIL PROVIDER] (email), Google (only if you choose Google sign-in), and [HOSTING PROVIDER] (hosting). [STATE where each stores data, and the safeguards used for transfers outside Kenya.]",
  ] },
  { heading: "How long we keep it", body: [
    "Account and profile data: until you delete your account. After deletion we remove your profile, contact details, messages and notification history.",
    "Payment and registration records: kept for [7] years with your personal details removed, for our financial records. [ACCOUNTANT/LAWYER: confirm the period.]",
    "Sent messages: about 90 days. Resolved support messages: about 12 months. Deleted data may remain in backups until they are overwritten. [CONFIRM backup period.]",
  ] },
  { heading: "Your rights", body: [
    "You can see and download your data, correct it, and delete your account yourself from your account page. You can also ask us to restrict or stop certain uses of your data, or contact us about anything here, through the Help page.",
    "We respond within the time Kenyan law requires. If you aren't happy, you can complain to the Office of the Data Protection Commissioner (ODPC).",
  ] },
  { heading: "Security", body: [
    "Passwords are stored only as hashes, connections use HTTPS, and access to admin tools is restricted and logged.",
  ] },
  { heading: "Children", body: [
    "Runners under 18 may enter only with a parent or guardian's consent. [LAWYER: confirm the rules for processing children's data.]",
  ] },
  { heading: "Cookies", body: [
    "We use one essential cookie to keep you signed in. We don't use advertising or tracking cookies.",
  ] },
  { heading: "Changes", body: [
    "If this notice changes in a way that matters, we'll ask you to accept the new version.",
  ] },
]

export default function PrivacyPage() {
  return <LegalPage title="Privacy Notice" sections={SECTIONS} />
}