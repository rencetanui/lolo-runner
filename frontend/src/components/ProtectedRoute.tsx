import { Navigate, Outlet, useLocation } from "react-router-dom"
import { useMe } from "@/api/auth"
import { Skeleton } from "@/components/ui/skeleton"

export default function ProtectedRoute() {
  const { data: user, isLoading } = useMe()
  const location = useLocation()

  if (isLoading) return <Skeleton className="m-4 mx-auto h-40 max-w-md" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <Outlet />
}