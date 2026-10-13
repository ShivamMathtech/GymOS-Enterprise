import type { AuthInfo } from "./types";
const BASE = import.meta.env.VITE_API_BASE || "/api/v1";
let access: string | null = null;
let renewing: Promise<boolean> | null = null;
export function setAccess(token: string | null) {
  access = token;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export function csrf() {
  return decodeURIComponent(
    document.cookie
      .split("; ")
      .find((c) => c.startsWith("gymos_csrf="))
      ?.split("=")
      .slice(1)
      .join("=") || "",
  );
}
async function refresh() {
  if (!renewing)
    renewing = (async () => {
      try {
        const r = await fetch(BASE + "/auth/refresh", {
          method: "POST",
          credentials: "include",
          headers: { "X-CSRF-Token": csrf() },
        });
        if (!r.ok) {
          access = null;
          return false;
        }
        const d = await r.json();
        access = d.access_token;
        return true;
      } catch {
        return false;
      } finally {
        renewing = null;
      }
    })();
  return renewing;
}
export async function api<T = unknown>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (access) headers.set("Authorization", "Bearer " + access);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (path.startsWith("/auth/")) headers.set("X-CSRF-Token", csrf());
  const response = await fetch(BASE + path, {
    ...options,
    headers,
    credentials: "include",
  });
  if (
    response.status === 401 &&
    retry &&
    !path.startsWith("/auth/login") &&
    !path.startsWith("/auth/register") &&
    (await refresh())
  )
    return api<T>(path, options, false);
  if (!response.ok) {
    const d = await response.json().catch(() => ({}));
    const message = d.error?.message || "Request failed";
    const fields = (d.error?.fields || [])
      .map(
        (f: { field: string; message: string }) => f.field + ": " + f.message,
      )
      .join("; ");
    throw new ApiError(
      response.status,
      message + (fields ? " — " + fields : ""),
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
export async function restore() {
  if (!csrf()) return null;
  if (!(await refresh())) return null;
  return api<AuthInfo>("/auth/me");
}
export async function fileRequest(
  path: string,
  filename: string,
  open = false,
) {
  const get = () =>
    fetch(BASE + path, {
      headers: { Authorization: "Bearer " + access },
      credentials: "include",
    });
  let r = await get();
  if (r.status === 401 && (await refresh())) r = await get();
  if (!r.ok)
    throw new Error((await r.json()).error?.message || "Download failed");
  const url = URL.createObjectURL(await r.blob());
  if (open) {
    const win = window.open(url, "_blank", "noopener,noreferrer");
    if (!win) {
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
    }
  } else {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
  }
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
export const send = (data: unknown) => ({
  method: "POST",
  body: JSON.stringify(data),
});
export const key = () => crypto.randomUUID();
export function currency(value: unknown, code = "INR") {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: code,
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}
export function localDay() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
