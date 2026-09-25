let token = sessionStorage.getItem("techsignal-token") || "";
const apiBase = (import.meta.env.VITE_API_BASE || "/api").replace(/\/$/, "");
export const apiUrl = (path: string) => `${apiBase}${path}`;
export function setToken(value: string) {
  token = value;
  value
    ? sessionStorage.setItem("techsignal-token", value)
    : sessionStorage.removeItem("techsignal-token");
}
export async function api<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if (response.status === 401)
      window.dispatchEvent(new Event("techsignal-unauthorized"));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail || `Request failed (${response.status})`),
    );
  }
  return response.json();
}
export const post = <T = any>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const put = <T = any>(path: string, body: unknown) =>
  api<T>(path, { method: "PUT", body: JSON.stringify(body) });
export async function download(id: string, format: "pdf" | "md") {
  const response = await fetch(apiUrl(`/reports/${id}/export?format=${format}`), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Report download failed");
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `techsignal-${id}.${format}`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
