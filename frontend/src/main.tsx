import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import "./index.css"

import RoleRoute from "./components/organizer/RoleRoute"
import OrganizerEventsPage from "./pages/OrganizerEventsPage"
import OrganizerEventPage from "./pages/OrganizerEventPage"
import OrganizerNewEventPage from "./pages/OrganizerNewEventPage"
import EventsPage from "./pages/EventsPage"
import EventDetailPage from "./pages/EventDetailPage"
import LoginPage from "./pages/LoginPage"
import SignupPage from "./pages/SignupPage"
import AccountPage from "./pages/AccountPage"
import ProtectedRoute from "./components/ProtectedRoute"
import Layout from "./components/Layout"
import ProfilePage from "./pages/ProfilePage"
import RegisterPage from "./pages/RegisterPage"
import RegistrationDetailPage from "./pages/RegistrationDetailPage"
import ChangePasswordPage from "./pages/ChangePasswordPage"
import ForgotPasswordPage from "./pages/ForgotPasswordPage"
import ResetPasswordPage from "./pages/ResetPasswordPage"
import VerifyEmailPage from "./pages/VerifyEmailPage"
import AdminPaymentPage from "./pages/AdminPaymentPage"
import AdminPaymentsPage from "./pages/AdminPaymentsPage"
import AdminRefundPage from "./pages/AdminRefundPage"
import AdminRefundsPage from "./pages/AdminRefundsPage"
import { Navigate } from "react-router-dom"

const queryClient = new QueryClient()

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<EventsPage />} />
              <Route path="/events/:id" element={<EventDetailPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/verify-email" element={<VerifyEmailPage />} />
              <Route element={<ProtectedRoute />}>
                <Route path="/account" element={<AccountPage />} />
                <Route path="/account/profile" element={<ProfilePage />} />
                <Route path="/events/:id/register" element={<RegisterPage />} />
                <Route path="/registrations/:id" element={<RegistrationDetailPage />} />
                <Route path="/account/password" element={<ChangePasswordPage />} />
                <Route element={<RoleRoute roles={["organizer", "admin"]} />}>
                  <Route path="/organizer/events" element={<OrganizerEventsPage />} />
                  <Route path="/organizer/events/new" element={<OrganizerNewEventPage />} />
                  <Route path="/organizer/events/:id" element={<OrganizerEventPage />} />
                </Route>
                <Route element={<RoleRoute roles={["admin"]} />}>
                  <Route path="/admin" element={<Navigate to="/admin/payments" replace />} />
                  <Route path="/admin/payments" element={<AdminPaymentsPage />} />
                  <Route path="/admin/payments/:id" element={<AdminPaymentPage />} />
                  <Route path="/admin/refunds" element={<AdminRefundsPage />} />
                  <Route path="/admin/refunds/:id" element={<AdminRefundPage />} />
                </Route>
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)