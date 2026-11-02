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