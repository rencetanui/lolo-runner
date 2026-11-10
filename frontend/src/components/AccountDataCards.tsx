import { useState } from "react"
import { Link } from "react-router-dom"
import { useMe } from "@/api/auth"
import { useDeletionCheck, useDownloadMyData, useRequestDeletion, useUpdateName } from "@/api/account"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

function DetailsCard() {
  const { data: user } = useMe()
  const update = useUpdateName()
  const [name, setName] = useState<string | null>(null)
  const value = name ?? user?.full_name ?? ""
  return (
    <Card>
      <CardHeader>
        <CardTitle>Your details</CardTitle>
        <CardDescription>
          Your email is {user?.email}. To change it, contact us through the <Link to="/help" className="underline">Help page</Link>.
          Your runner profile is edited separately above.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-3"
          onSubmit={(e) => { e.preventDefault(); update.mutate(value.trim(), { onSuccess: () => setName(null) }) }}
        >
          <div className="space-y-2">
            <Label htmlFor="acc-name">Full name</Label>
            <Input id="acc-name" required minLength={2} maxLength={100} value={value} onChange={(e) => setName(e.target.value)} />
          </div>
          {update.error && <Alert variant="destructive"><AlertDescription>{update.error.message}</AlertDescription></Alert>}
          {update.isSuccess && name === null && <Alert><AlertDescription>Saved.</AlertDescription></Alert>}
          <Button type="submit" size="sm" disabled={update.isPending || value.trim() === user?.full_name}>
            {update.isPending ? "Saving…" : "Save name"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function DataCard() {
  const download = useDownloadMyData()
  return (
    <Card>
      <CardHeader>
        <CardTitle>Your data</CardTitle>
        <CardDescription>
          Download everything we hold about you as a file. See the <Link to="/privacy" className="underline">Privacy Notice</Link> for
          how we use it. You can download up to three times a day.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {download.error && <Alert variant="destructive"><AlertDescription>{download.error.message}</AlertDescription></Alert>}
        <Button variant="outline" size="sm" disabled={download.isPending} onClick={() => download.mutate()}>
          {download.isPending ? "Preparing…" : "Download my data"}
        </Button>
      </CardContent>
    </Card>
  )
}

function DeleteCard() {
  const check = useDeletionCheck()
  const request = useRequestDeletion()
  return (
    <Card>
      <CardHeader>
        <CardTitle>Delete my account</CardTitle>
        <CardDescription>
          This permanently removes your profile, contact details and messages. Payment and registration records are kept
          without your personal details. We'll email you a link to confirm.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {check.data && !check.data.can_delete && (
          <Alert>
            <AlertDescription>
              <ul className="list-disc space-y-1 pl-4">
                {check.data.blockers.map((b) => <li key={b.code}>{b.message}</li>)}
              </ul>
            </AlertDescription>
          </Alert>
        )}
        {request.isSuccess && <Alert><AlertDescription>{request.data.message}</AlertDescription></Alert>}
        {request.error && <Alert variant="destructive"><AlertDescription>{request.error.message}</AlertDescription></Alert>}
        {check.data?.can_delete && !request.isSuccess && (
          <Button
            variant="destructive"
            size="sm"
            disabled={request.isPending}
            onClick={() => { if (window.confirm("Email me a link to delete my account?")) request.mutate() }}
          >
            {request.isPending ? "Sending…" : "Delete my account…"}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

export function AccountDataCards() {
  return (
    <>
      <DetailsCard />
      <DataCard />
      <DeleteCard />
    </>
  )
}