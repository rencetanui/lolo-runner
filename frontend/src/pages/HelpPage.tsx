import { useState } from "react"
import { Link } from "react-router-dom"
import { useMe } from "@/api/auth"
import { useSendSupport } from "@/api/support"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

const FAQ = [
  ["How do I register for a race?", "Open the race, choose a distance, and follow the steps. You'll need an account, a verified email address and your runner profile. Paid entries are confirmed once your M-Pesa payment goes through."],
  ["I didn't get the M-Pesa prompt.", "Check that the number is a Safaricom number you can use, and that your phone has signal. Then wait a minute and try again from your registration page. Your place is held for 30 minutes."],
  ["I paid but my registration still says awaiting payment.", "Give it a few minutes and click \"I've paid, check now\" on the registration page. If it still hasn't updated, contact us below with your M-Pesa code."],
  ["I didn't get a confirmation email.", "Check your spam folder. You can also see every registration, and its status, on your account page."],
  ["How do I cancel, and will I get a refund?", "Cancel from your registration page. Before you confirm, we show what will happen to your money. Refunds depend on each event's refund deadline, and see the Refund Policy for the details."],
  ["Can I change my distance?", "Cancel your registration and register again for the new distance, if spots and the registration window allow."],
  ["I forgot my password.", "Use \"Forgot your password?\" on the log-in page. If you signed up with Google, just use Continue with Google."],
  ["How do I see, correct or delete my data?", "From your account page you can download your data, change your details and delete your account. See the Privacy Notice for more."],
] as const

const TOPICS = [
  ["registration", "Registration"], ["payment", "Payment"], ["refund", "Refund"],
  ["account", "My account"], ["event", "An event"], ["other", "Something else"],
] as const

function ContactForm() {
  const { data: user } = useMe()
  const send = useSendSupport()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [topic, setTopic] = useState<(typeof TOPICS)[number][0]>("other")
  const [message, setMessage] = useState("")
  const [website, setWebsite] = useState("")        // hidden spam trap: real people never fill it in

  if (send.isSuccess)
    return (
      <Alert>
        <AlertTitle>Message sent</AlertTitle>
        <AlertDescription>
          {send.data.message} Your reference is <strong>{send.data.reference}</strong>.
        </AlertDescription>
      </Alert>
    )

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        send.mutate({
          name: (name || user?.full_name || "").trim(),
          email: (email || user?.email || "").trim(),
          topic,
          message: message.trim(),
          website,
        })
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="c-name">Your name</Label>
          <Input id="c-name" required minLength={2} maxLength={100} autoComplete="name"
            value={name || user?.full_name || ""} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="c-email">Email</Label>
          <Input id="c-email" type="email" required autoComplete="email"
            value={email || user?.email || ""} onChange={(e) => setEmail(e.target.value)} />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="c-topic">What's it about?</Label>
        <select id="c-topic" className="h-9 w-full rounded-md border bg-background px-2 text-sm"
          value={topic} onChange={(e) => setTopic(e.target.value as typeof topic)}>
          {TOPICS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="c-message">Message</Label>
        <Textarea id="c-message" required minLength={10} maxLength={2000} rows={5}
          value={message} onChange={(e) => setMessage(e.target.value)}
          placeholder="Tell us what happened. Include your M-Pesa code if it's about a payment." />
      </div>
      <div aria-hidden="true" className="absolute left-[-9999px] h-0 w-0 overflow-hidden">
        <label>Leave this empty<input tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} /></label>
      </div>
      {send.error && <Alert variant="destructive"><AlertDescription>{send.error.message}</AlertDescription></Alert>}
      <Button type="submit" disabled={send.isPending}>{send.isPending ? "Sending…" : "Send message"}</Button>
    </form>
  )
}

export default function HelpPage() {
  return (
    <main className="mx-auto max-w-3xl space-y-8 p-4 sm:p-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold sm:text-3xl">Help and contact</h1>
        <p className="text-muted-foreground">
          Quick answers first. If you can't find yours, send us a message. See also the{" "}
          <Link to="/refund-policy" className="underline">Refund Policy</Link> and{" "}
          <Link to="/privacy" className="underline">Privacy Notice</Link>.
        </p>
      </header>

      <section className="space-y-2">
        {FAQ.map(([q, a]) => (
          <details key={q} className="rounded-md border p-3">
            <summary className="cursor-pointer font-medium">{q}</summary>
            <p className="mt-2 text-sm text-muted-foreground">{a}</p>
          </details>
        ))}
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Contact us</CardTitle>
          <CardDescription>We reply by email. Please don't include your M-Pesa PIN or passwords.</CardDescription>
        </CardHeader>
        <CardContent><ContactForm /></CardContent>
      </Card>
    </main>
  )
}