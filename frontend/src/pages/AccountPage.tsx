import { Link } from "react-router-dom"
import { useMe } from "@/api/auth"
import { useProfile } from "@/api/profile"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { MyRegistrations } from "@/components/MyRegistration"

export default function AccountPage() {
  const { data: user } = useMe()
  const { data: profile, isLoading } = useProfile()

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold sm:text-3xl">My account</h1>
        <p className="text-muted-foreground">{user?.email}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Runner profile</CardTitle>
          <CardDescription>
            {profile ? "Your details for race registration." : "You'll need this before you can register for a race."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading && <Skeleton className="h-16" />}
          {profile && (
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div><dt className="text-muted-foreground">Age category</dt><dd className="font-medium">{profile.age_category}</dd></div>
              <div><dt className="text-muted-foreground">Phone</dt><dd className="font-medium">{profile.phone}</dd></div>
              <div><dt className="text-muted-foreground">Emergency contact</dt><dd className="font-medium">{profile.emergency_contact_name}</dd></div>
              <div><dt className="text-muted-foreground">T-shirt</dt><dd className="font-medium">{profile.tshirt_size}</dd></div>
            </dl>
          )}
          {!isLoading && (
            <Link to="/account/profile" className={buttonVariants()}>{profile ? "Edit profile" : "Set up profile"}</Link>
          )}
        </CardContent>
      </Card>
      <MyRegistrations />
    </main>
  )
}