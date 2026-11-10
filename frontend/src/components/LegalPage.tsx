import { useLegalVersion } from "@/api/legal"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

export type LegalSection = { heading: string; body: string[] }

// [Bracketed text] is a placeholder for someone to fill in or decide. It's highlighted so it can't be missed.
function Text({ children }: { children: string }) {
  return (
    <>
      {children.split(/(\[[^\]]+\])/).map((part, i) =>
        /^\[[^\]]+\]$/.test(part)
          ? <mark key={i} className="rounded bg-yellow-200 px-1 text-foreground">{part}</mark>
          : <span key={i}>{part}</span>,
      )}
    </>
  )
}

export function LegalPage({ title, sections }: { title: string; sections: LegalSection[] }) {
  const { data: version } = useLegalVersion()
  return (
    <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold sm:text-3xl">{title}</h1>
        {version && <p className="text-sm text-muted-foreground">Version {version}</p>}
      </header>
      <Alert variant="destructive">
        <AlertTitle>Draft: not yet reviewed by a lawyer</AlertTitle>
        <AlertDescription>
          Replace every highlighted [placeholder] and have this reviewed before launch. Remove this notice afterwards.
        </AlertDescription>
      </Alert>
      {sections.map((s, i) => (
        <section key={s.heading} className="space-y-2">
          <h2 className="text-lg font-semibold">{i + 1}. {s.heading}</h2>
          {s.body.map((p, j) => (
            <p key={j} className="text-sm leading-relaxed"><Text>{p}</Text></p>
          ))}
        </section>
      ))}
    </main>
  )
}