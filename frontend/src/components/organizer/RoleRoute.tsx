import { Outlet } from "react-router-dom"
import { useMe } from "@/api/auth"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

// UX only: the server enforces roles on every request.
export default function RoleRoute({ roles }: { roles: string[] }) {
  const { data: user } = useMe()
  if (!user || !roles.includes(user.role)) {
    return (
      <main className="mx-auto max-w-2xl p-4">
        <Alert variant="destructive">
          <AlertTitle>No access</AlertTitle>
          <AlertDescription>This area is for event organizers.</AlertDescription>
        </Alert>
      </main>
    )
  }
  return <Outlet />
}