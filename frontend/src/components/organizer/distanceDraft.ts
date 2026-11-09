import type { DistanceAdmin, DistanceInput } from "@/api/organizer"

// Form fields stay strings while typing; they're converted when saving.
export type DistanceDraft = {
  name: string
  km: string
  fee: string
  capacity: string
  min_age: string
  start_time: string
  cutoff_minutes: string
}

export const emptyDraft = (): DistanceDraft => ({
  name: "", km: "", fee: "", capacity: "", min_age: "12", start_time: "", cutoff_minutes: "",
})

export const toDraft = (d: DistanceAdmin): DistanceDraft => ({
  name: d.name,
  km: String(Number(d.km)),
  fee: String(Number(d.fee)),
  capacity: String(d.capacity),
  min_age: String(d.min_age),
  start_time: d.start_time ? d.start_time.slice(0, 5) : "",
  cutoff_minutes: d.cutoff_minutes ? String(d.cutoff_minutes) : "",
})

export function draftError(d: DistanceDraft): string | null {
  const label = d.name.trim() || "Distance"
  if (!d.name.trim()) return "Give each distance a name, e.g. 10K."
  if (!(Number(d.km) > 0)) return `${label}: enter the distance in km.`
  const fee = Number(d.fee)
  if (d.fee === "" || !Number.isInteger(fee) || fee < 0)
    return `${label}: the entry fee must be a whole number of shillings (0 for free).`
  const capacity = Number(d.capacity)
  if (!Number.isInteger(capacity) || capacity < 1) return `${label}: capacity must be at least 1.`
  const age = Number(d.min_age)
  if (!Number.isInteger(age) || age < 0 || age > 100) return `${label}: minimum age must be between 0 and 100.`
  if (d.cutoff_minutes !== "") {
    const cutoff = Number(d.cutoff_minutes)
    if (!Number.isInteger(cutoff) || cutoff < 15 || cutoff > 1440)
      return `${label}: the cut-off must be between 15 and 1440 minutes.`
  }
  return null
}

export const toInput = (d: DistanceDraft): DistanceInput => ({
  name: d.name.trim(),
  km: Number(d.km),
  fee: Number(d.fee),
  capacity: Number(d.capacity),
  min_age: Number(d.min_age),
  start_time: d.start_time || null,
  cutoff_minutes: d.cutoff_minutes ? Number(d.cutoff_minutes) : null,
})