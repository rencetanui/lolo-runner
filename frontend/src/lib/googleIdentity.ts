type CredentialResponse = { credential: string }

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: { client_id: string; callback: (response: CredentialResponse) => void }) => void
          renderButton: (parent: HTMLElement, options: Record<string, string | number>) => void
        }
      }
    }
  }
}

let loading: Promise<void> | null = null

export function loadGoogleIdentity(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve()
  loading ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement("script")
    script.src = "https://accounts.google.com/gsi/client"
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => {
      loading = null
      reject(new Error("Could not load Google sign-in. Check your connection or ad blocker."))
    }
    document.head.appendChild(script)
  })
  return loading
}