export const formatDate = (iso: string) =>
  new Intl.DateTimeFormat("en-KE", {
    weekday: "short", day: "numeric", month: "short", year: "numeric",
  }).format(new Date(`${iso}T00:00:00`))

export const formatKES = (amount: string | number) =>
  new Intl.NumberFormat("en-KE", {
    style: "currency", currency: "KES", maximumFractionDigits: 0,
  }).format(Number(amount))

export const formatKm = (km: string | number) => `${Number(km)} km`

// ISO dates (YYYY-MM-DD) compare correctly as plain strings
export function registrationState(opens: string, closes: string) {
  const today = new Date().toLocaleDateString("en-CA")
  if (today < opens) return "soon" as const
  if (today > closes) return "closed" as const
  return "open" as const
}

export function ageOn(dob: string, on: string) {
  const d = new Date(`${dob}T00:00:00`)
  const e = new Date(`${on}T00:00:00`)
  let age = e.getFullYear() - d.getFullYear()
  const m = e.getMonth() - d.getMonth()
  if (m < 0 || (m === 0 && e.getDate() < d.getDate())) age--
  return age
}

export const formatDateTime = (iso: string) =>
  new Intl.DateTimeFormat("en-KE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso))

export function formatTime(t: string) {
  const [h, m] = t.split(":").map(Number)
  return new Intl.DateTimeFormat("en-KE", { hour: "numeric", minute: "2-digit" }).format(new Date(2000, 0, 1, h, m))
}