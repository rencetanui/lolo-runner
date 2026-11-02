import { useState } from "react"
import { Link } from "react-router-dom"
import { useProfile, useSaveProfile, type Profile, type ProfileInput } from "@/api/profile"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { COUNTIES } from "@/lib/kenya"

const GENDERS = [
  { value: "female", label: "Female" },
  { value: "male", label: "Male" },
  { value: "other", label: "Other" },
]
const SIZES = ["XS", "S", "M", "L", "XL", "XXL"]

type FormState = {
  date_of_birth: string
  gender: string
  phone: string
  county: string
  club: string
  tshirt_size: string
  emergency_contact_name: string
  emergency_contact_phone: string
  emergency_contact_relationship: string
  medical_notes: string
}

function Field({ id, label, hint, children }: {
  id: string; label: string; hint?: string; children: React.ReactNode
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

function ProfileForm({ initial }: { initial: Profile | null }) {
  const save = useSaveProfile()
  const [localError, setLocalError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [form, setForm] = useState<FormState>({
    date_of_birth: initial?.date_of_birth ?? "",
    gender: initial?.gender ?? "",
    phone: initial?.phone ?? "",
    county: initial?.county ?? "",
    club: initial?.club ?? "",
    tshirt_size: initial?.tshirt_size ?? "",
    emergency_contact_name: initial?.emergency_contact_name ?? "",
    emergency_contact_phone: initial?.emergency_contact_phone ?? "",
    emergency_contact_relationship: initial?.emergency_contact_relationship ?? "",
    medical_notes: initial?.medical_notes ?? "",
  })

  const set = (key: keyof FormState) => (value: string) => {
    setForm((f) => ({ ...f, [key]: value }))
    setSaved(false)
  }
  const text = (key: keyof FormState) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      set(key)(e.target.value),
  })

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.gender || !form.tshirt_size) {
      setLocalError("Please choose your gender and t-shirt size.")
      return
    }
    setLocalError(null)
    const body: ProfileInput = {
      ...form,
      gender: form.gender as ProfileInput["gender"],
      tshirt_size: form.tshirt_size as ProfileInput["tshirt_size"],
      county: form.county || null,
      club: form.club.trim() || null,
      medical_notes: form.medical_notes.trim() || null,
    }
    save.mutate(body, { onSuccess: () => setSaved(true) })
  }

  const today = new Date().toLocaleDateString("en-CA")

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>About you</CardTitle>
          <CardDescription>We use this to place you in the right race category.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field id="dob" label="Date of birth">
            <Input id="dob" type="date" required max={today} {...text("date_of_birth")} />
          </Field>
          <Field id="gender" label="Gender" hint="Used for race categories.">
            <Select value={form.gender} onValueChange={set("gender")}>
              <SelectTrigger id="gender"><SelectValue placeholder="Select" /></SelectTrigger>
              <SelectContent>
                {GENDERS.map((g) => <SelectItem key={g.value} value={g.value}>{g.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          <Field id="phone" label="Phone number">
            <Input id="phone" type="tel" autoComplete="tel" required placeholder="0712 345 678" {...text("phone")} />
          </Field>
          <Field id="county" label="County (optional)">
            <Select value={form.county} onValueChange={set("county")}>
              <SelectTrigger id="county"><SelectValue placeholder="Select" /></SelectTrigger>
              <SelectContent>
                {COUNTIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          <Field id="club" label="Running club (optional)">
            <Input id="club" maxLength={100} {...text("club")} />
          </Field>
          <Field id="size" label="T-shirt size">
            <Select value={form.tshirt_size} onValueChange={set("tshirt_size")}>
              <SelectTrigger id="size"><SelectValue placeholder="Select" /></SelectTrigger>
              <SelectContent>
                {SIZES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Emergency contact</CardTitle>
          <CardDescription>Someone we can call if something happens on race day.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field id="ec-name" label="Full name">
            <Input id="ec-name" required minLength={2} {...text("emergency_contact_name")} />
          </Field>
          <Field id="ec-phone" label="Phone number">
            <Input id="ec-phone" type="tel" required {...text("emergency_contact_phone")} />
          </Field>
          <Field id="ec-rel" label="Relationship">
            <Input id="ec-rel" required minLength={2} placeholder="e.g. Sister" {...text("emergency_contact_relationship")} />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Medical information (optional)</CardTitle>
          <CardDescription>
            Conditions, allergies, or medication that medical staff should know about.
            Only you and authorized race medical staff can see this.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea id="medical" rows={4} maxLength={500} {...text("medical_notes")} />
        </CardContent>
      </Card>

      {(localError || save.error) && (
        <Alert variant="destructive">
          <AlertDescription>{localError ?? save.error?.message}</AlertDescription>
        </Alert>
      )}
      {saved && (
        <Alert>
          <AlertDescription>
            Profile saved. <Link to="/" className="underline">Browse races →</Link>
          </AlertDescription>
        </Alert>
      )}

      <Button type="submit" size="lg" className="w-full sm:w-auto" disabled={save.isPending}>
        {save.isPending ? "Saving…" : "Save profile"}
      </Button>
    </form>
  )
}

export default function ProfilePage() {
  const { data: profile, isLoading, error } = useProfile()

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      <div>
        <Link to="/account" className="text-sm text-muted-foreground hover:underline">← My account</Link>
        <h1 className="mt-2 text-2xl font-bold sm:text-3xl">Runner profile</h1>
      </div>
      {isLoading && <Skeleton className="h-96" />}
      {error && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}
      {!isLoading && !error && <ProfileForm initial={profile ?? null} />}
    </main>
  )
}