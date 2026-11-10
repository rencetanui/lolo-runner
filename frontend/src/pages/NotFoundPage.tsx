import { Link } from "react-router-dom"
import { buttonVariants } from "@/components/ui/button"

export default function NotFoundPage() {
  return (
    <main className="mx-auto max-w-md space-y-4 p-8 text-center">
      <h1 className="text-3xl font-bold">Page not found</h1>
      <p className="text-muted-foreground">The page you're looking for doesn't exist or has moved.</p>
      <Link to="/" className={buttonVariants()}>Browse races</Link>
    </main>
  )
}