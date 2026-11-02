import { useMe } from "@/api/auth"

export default function AccountPage() {
  const { data: user } = useMe()
  return (
    <main className="mx-auto max-w-3xl p-4 sm:p-6">
      <h1 className="text-2xl font-bold">My account</h1>
      <p className="mt-2 text-muted-foreground">{user?.email} · {user?.role}</p>
    </main>
  )
}