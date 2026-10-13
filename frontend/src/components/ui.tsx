import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type FormEvent,
} from "react";
import {
  X,
  ChevronLeft,
  ChevronRight,
  Inbox,
  AlertCircle,
  LoaderCircle,
} from "lucide-react";
import type { Row, Page } from "../types";
export function ErrorBox({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <div className="error" role="alert">
      <AlertCircle size={18} />
      <span>{error instanceof Error ? error.message : String(error)}</span>
      {retry && <button onClick={retry}>Retry</button>}
    </div>
  );
}
export function Loading() {
  return (
    <div className="skeletons" aria-label="Loading" role="status">
      {[1, 2, 3].map((i) => (
        <div className="skeleton" key={i} />
      ))}
    </div>
  );
}
export function Empty({
  text = "No records yet. Add your first record to get started.",
}: {
  text?: string;
}) {
  return (
    <div className="empty">
      <Inbox size={32} />
      <p>{text}</p>
    </div>
  );
}
export function Badge({ value }: { value: unknown }) {
  const v = String(value ?? "—");
  return (
    <span
      className={
        "badge " +
        (["active", "paid", "operational", "completed", "true"].includes(v)
          ? "good"
          : [
                "expired",
                "cancelled",
                "inactive",
                "archived",
                "false",
                "no_show",
              ].includes(v)
            ? "muted"
            : [
                  "pending_payment",
                  "partial",
                  "maintenance",
                  "frozen",
                  "unpaid",
                ].includes(v)
              ? "warn"
              : "blue")
      }
    >
      {v.replaceAll("_", " ")}
    </span>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    el?.showModal();
    return () => el?.close();
  }, []);
  return (
    <dialog ref={ref} onCancel={onClose} aria-labelledby="dialog-title">
      <div className="modal-head">
        <h2 id="dialog-title">{title}</h2>
        <button className="icon" onClick={onClose} aria-label="Close dialog">
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export type Option = { value: string; label: string };
export type Field = {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  options?: Option[];
  defaultValue?: unknown;
  hint?: string;
  min?: number;
  max?: number;
  step?: string;
};
export function Form({
  fields,
  submit,
  label = "Save",
  initial = {},
  onDone,
}: {
  fields: Field[];
  submit: (
    data: Record<string, unknown>,
    requestKey: string,
  ) => Promise<unknown>;
  label?: string;
  initial?: Record<string, unknown>;
  onDone?: () => void;
}) {
  const [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const attempt = useRef({ fingerprint: "", key: "" });
  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const fd = new FormData(e.currentTarget);
    const values: Record<string, unknown> = {};
    for (const f of fields) {
      const v = fd.get(f.name);
      if (f.type === "multiselect") {
        values[f.name] = fd.getAll(f.name).map(String);
        continue;
      }
      values[f.name] =
        f.type === "checkbox"
          ? v === "on"
          : f.type === "number"
            ? v === ""
              ? null
              : Number(v)
            : v === "" && !f.required
              ? f.options ||
                ["email", "datetime-local", "date", "money"].includes(
                  f.type || "",
                )
                ? null
                : ""
              : v;
    }
    try {
      const fingerprint = JSON.stringify(values);
      if (attempt.current.fingerprint !== fingerprint) {
        attempt.current = { fingerprint, key: crypto.randomUUID() };
      }
      await submit(values, attempt.current.key);
      attempt.current = { fingerprint: "", key: "" };
      onDone?.();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={onSubmit} className="form-grid">
      {fields.map((f) => (
        <label key={f.name} className={f.type === "textarea" ? "wide" : ""}>
          <span>
            {f.label}
            {f.required && <span className="required"> *</span>}
          </span>
          {f.options ? (
            <select
              name={f.name}
              required={f.required}
              multiple={f.type === "multiselect"}
              defaultValue={
                f.type === "multiselect"
                  ? ((initial[f.name] ?? f.defaultValue ?? []) as string[])
                  : String(initial[f.name] ?? f.defaultValue ?? "")
              }
            >
              {f.type !== "multiselect" && <option value="">Select…</option>}
              {f.options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          ) : f.type === "textarea" ? (
            <textarea
              name={f.name}
              defaultValue={String(initial[f.name] ?? f.defaultValue ?? "")}
              required={f.required}
              rows={3}
            />
          ) : (
            <input
              name={f.name}
              type={f.type === "money" ? "number" : f.type || "text"}
              min={f.min ?? (f.type === "money" ? 0 : undefined)}
              max={f.max}
              step={f.step ?? (f.type === "money" ? "0.01" : undefined)}
              defaultValue={
                f.type !== "checkbox"
                  ? String(initial[f.name] ?? f.defaultValue ?? "")
                  : undefined
              }
              defaultChecked={
                f.type === "checkbox"
                  ? Boolean(initial[f.name] ?? f.defaultValue)
                  : undefined
              }
              required={f.required}
              autoComplete={f.type === "password" ? "new-password" : undefined}
            />
          )}{" "}
          {f.hint && <small>{f.hint}</small>}
        </label>
      ))}
      {error != null && (
        <div className="wide">
          <ErrorBox error={error} />
        </div>
      )}
      <div className="form-actions wide">
        <button type="submit" className="primary" disabled={busy}>
          {busy ? (
            <>
              <LoaderCircle size={16} className="spin" />
              Saving…
            </>
          ) : (
            label
          )}
        </button>
      </div>
    </form>
  );
}
export type Column = {
  key: string;
  label: string;
  render?: (row: Row) => ReactNode;
};
export function Table({
  data,
  columns,
  actions,
  onPage,
  page = 1,
}: {
  data: Page | Row[];
  columns: Column[];
  actions?: (row: Row) => ReactNode;
  onPage?: (p: number) => void;
  page?: number;
}) {
  const rows = Array.isArray(data) ? data : data.items;
  if (!rows.length) return <Empty />;
  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} scope="col">
                  {c.label}
                </th>
              ))}
              {actions && <th scope="col">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                {columns.map((c) => (
                  <td key={c.key}>
                    {c.render ? (
                      c.render(row)
                    ) : typeof row[c.key] === "boolean" ? (
                      <Badge value={row[c.key]} />
                    ) : (
                      String(row[c.key] ?? "—")
                    )}
                  </td>
                ))}
                {actions && <td className="actions">{actions(row)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!Array.isArray(data) && (
        <div className="pagination">
          <span>
            {data.total} records · Page {page} of{" "}
            {Math.max(1, Math.ceil(data.total / data.size))}
          </span>
          <button
            className="icon"
            aria-label="Previous page"
            disabled={page <= 1}
            onClick={() => onPage?.(page - 1)}
          >
            <ChevronLeft size={18} />
          </button>
          <button
            className="icon"
            aria-label="Next page"
            disabled={page * data.size >= data.total}
            onClick={() => onPage?.(page + 1)}
          >
            <ChevronRight size={18} />
          </button>
        </div>
      )}
    </>
  );
}
export function Confirm({
  title,
  message,
  onConfirm,
  onClose,
}: {
  title: string;
  message: string;
  onConfirm: () => Promise<unknown>;
  onClose: () => void;
}) {
  const [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  return (
    <Modal title={title} onClose={onClose}>
      <p className="modal-copy">{message}</p>
      {error != null && <ErrorBox error={error} />}
      <div className="form-actions">
        <button onClick={onClose}>Cancel</button>
        <button
          className="primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onConfirm();
              onClose();
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Working…" : "Confirm"}
        </button>
      </div>
    </Modal>
  );
}
