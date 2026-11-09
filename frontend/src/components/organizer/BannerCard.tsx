import { useRef, useState } from "react"
import { useDeleteBanner, useUploadBanner, type OrganizerEvent } from "@/api/organizer"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

const MAX_MB = 5

export function BannerCard({ event }: { event: OrganizerEvent }) {
  const upload = useUploadBanner(event.id)
  const remove = useDeleteBanner(event.id)
  const input = useRef<HTMLInputElement>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ""
    if (!file) return
    if (file.size > MAX_MB * 1024 * 1024) return setLocalError(`That file is over ${MAX_MB} MB. Choose a smaller image.`)
    setLocalError(null)
    upload.mutate(file)
  }

  const error = localError ?? upload.error?.message ?? remove.error?.message
  return (
    <Card>
      <CardHeader>
        <CardTitle>Banner image</CardTitle>
        <CardDescription>
          Shown on the event page and in link previews when someone shares the race. Use a wide photo, at least
          1200 pixels across. JPEG, PNG or WebP, up to {MAX_MB} MB. Location data in photos is removed.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {event.banner_url && (
          <img src={event.banner_url} alt="Current banner" className="max-h-56 w-full rounded-md object-cover" />
        )}
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={onPick} />
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="sm" disabled={upload.isPending} onClick={() => input.current?.click()}>
            {upload.isPending ? "Uploading…" : event.banner_url ? "Replace image" : "Upload image"}
          </Button>
          {event.banner_url && (
            <Button type="button" variant="outline" size="sm" disabled={remove.isPending} onClick={() => remove.mutate()}>
              Remove
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}