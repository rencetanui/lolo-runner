export async function shareEvent(id: string, name: string): Promise<"shared" | "copied" | "cancelled" | "failed"> {
  // The share link serves event-specific previews to WhatsApp and friends, then sends people to the real page.
  const url = `${window.location.origin}/share/e/${id}`
  if (navigator.share) {
    try {
      await navigator.share({ title: name, url })
      return "shared"
    } catch (e) {
      if ((e as DOMException).name === "AbortError") return "cancelled"
    }
  }
  try {
    await navigator.clipboard.writeText(url)
    return "copied"
  } catch {
    return "failed"
  }
}