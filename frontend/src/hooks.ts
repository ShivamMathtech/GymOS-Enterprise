import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { Row, Page } from "./types";
export async function allRows(path: string) {
  let page = 1;
  const rows: Row[] = [];
  while (true) {
    const d = await api<Page | Row[]>(
      path + (path.includes("?") ? "&" : "?") + "size=100&page=" + page,
    );
    if (Array.isArray(d)) return d;
    rows.push(...d.items);
    if (rows.length >= d.total || !d.items.length) return rows;
    page++;
  }
}
export function useRows(path: string, enabled = true) {
  return useQuery({
    queryKey: ["options", path],
    queryFn: () => allRows(path),
    enabled,
  });
}
export const options = (rows: Row[] | undefined, label = "name") =>
  (rows || []).map((r) => ({ value: r.id, label: String(r[label] ?? r.id) }));
export const rowName = (rows: Row[] | undefined, id: unknown) =>
  String(
    rows?.find((r) => r.id === id)?.name ||
      rows?.find((r) => r.id === id)?.number ||
      String(id ?? "—").slice(0, 8),
  );
