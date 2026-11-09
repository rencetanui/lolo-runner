import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { DistanceDraft } from "./distanceDraft"

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id} className="text-xs">{label}</Label>
      {children}
    </div>
  )
}

export function DistanceFields({
  idPrefix, value, onChange, lockBasics = false, minCapacity = 1,
}: {
  idPrefix: string
  value: DistanceDraft
  onChange: (d: DistanceDraft) => void
  lockBasics?: boolean
  minCapacity?: number
}) {
  const set = (key: keyof DistanceDraft) => (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange({ ...value, [key]: e.target.value })

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
      <Field id={`${idPrefix}-name`} label="Name">
        <Input id={`${idPrefix}-name`} placeholder="10K" value={value.name} onChange={set("name")} disabled={lockBasics} />
      </Field>
      <Field id={`${idPrefix}-km`} label="Distance (km)">
        <Input id={`${idPrefix}-km`} type="number" inputMode="decimal" min="0.01" step="0.01"
          value={value.km} onChange={set("km")} disabled={lockBasics} />
      </Field>
      <Field id={`${idPrefix}-fee`} label="Fee (KES)">
        <Input id={`${idPrefix}-fee`} type="number" inputMode="numeric" min="0" step="1"
          value={value.fee} onChange={set("fee")} />
      </Field>
      <Field id={`${idPrefix}-cap`} label="Capacity">
        <Input id={`${idPrefix}-cap`} type="number" inputMode="numeric" min={minCapacity} step="1"
          value={value.capacity} onChange={set("capacity")} />
      </Field>
      <Field id={`${idPrefix}-age`} label="Min. age">
        <Input id={`${idPrefix}-age`} type="number" inputMode="numeric" min="0" max="100" step="1"
          value={value.min_age} onChange={set("min_age")} disabled={lockBasics} />
      </Field>
      <Field id={`${idPrefix}-start`} label="Start time">
        <Input id={`${idPrefix}-start`} type="time" value={value.start_time} onChange={set("start_time")} />
      </Field>
      <Field id={`${idPrefix}-cutoff`} label="Cut-off (min)">
        <Input id={`${idPrefix}-cutoff`} type="number" inputMode="numeric" min="15" max="1440" step="1"
          value={value.cutoff_minutes} onChange={set("cutoff_minutes")} />
      </Field>
    </div>
  )
}