import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Plus, Download, Upload, ArrowUpRight } from "lucide-react";
import { api, send, fileRequest } from "../api";
import { useAuth } from "../auth";
import { useRows, options, rowName } from "../hooks";
import {
  Table,
  Modal,
  Form,
  Loading,
  ErrorBox,
  Badge,
  type Field,
} from "../components/ui";
import type { Page, Row, Member } from "../types";
export default function Members() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [q, setQ] = useState(""),
    [status, setStatus] = useState(""),
    [msStatus, setMsStatus] = useState(""),
    [page, setPage] = useState(1),
    [sort, setSort] = useState("name"),
    [modal, setModal] = useState<"create" | "import" | null>(null),
    [selected, setSelected] = useState<Row | null>(null),
    [error, setError] = useState<unknown>(null);
  const branches = useRows("/branches");
  const params = new URLSearchParams({
    q,
    page: String(page),
    sort,
    direction: "asc",
  });
  if (status) params.set("status", status);
  if (msStatus) params.set("membership_status", msStatus);
  const query = useQuery({
    queryKey: ["members", q, status, msStatus, page, sort],
    queryFn: () => api<Page<Member>>("/members?" + params),
  });
  const fields: Field[] = [
    {
      name: "branch_id",
      label: "Home branch",
      required: true,
      options: options(branches.data),
    },
    { name: "name", label: "Full name", required: true },
    { name: "phone", label: "Phone", required: true },
    { name: "email", label: "Email", type: "email" },
    ...(can("members.private")
      ? [
          { name: "emergency_contact", label: "Emergency contact" },
          { name: "notes", label: "Private notes", type: "textarea" },
        ]
      : []),
  ];
  const refresh = () => {
    qc.invalidateQueries();
    setModal(null);
    setSelected(null);
  };
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">MEMBER RELATIONSHIPS</div>
          <h1>A place for every member.</h1>
          <p>Keep profiles, access and history connected.</p>
        </div>
        <div className="page-actions">
          {can("members.export") && (
            <button
              onClick={() =>
                fileRequest("/members/export", "members.csv").catch(setError)
              }
            >
              <Download size={16} />
              Export CSV
            </button>
          )}
          {can("members.write") && (
            <>
              <button onClick={() => setModal("import")}>
                <Upload size={16} />
                Import
              </button>
              <button className="primary" onClick={() => setModal("create")}>
                <Plus size={17} />
                Register member
              </button>
            </>
          )}
        </div>
      </div>
      <section className="card">
        <div className="toolbar">
          <div className="search">
            <Search size={18} />
            <input
              aria-label="Search members"
              placeholder="Search name, phone or member ID…"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <select
            aria-label="Profile status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All profile statuses</option>
            {["active", "inactive", "archived"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <select
            aria-label="Membership status"
            value={msStatus}
            onChange={(e) => {
              setMsStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All memberships</option>
            {[
              "active",
              "expired",
              "pending_payment",
              "scheduled",
              "frozen",
              "none",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <select
            aria-label="Sort members"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="name">Name A–Z</option>
            <option value="member_code">Member ID</option>
            <option value="created_at">Registration date</option>
          </select>
        </div>
        {error != null && <ErrorBox error={error} />}{" "}
        {query.isLoading ? (
          <Loading />
        ) : query.error ? (
          <ErrorBox error={query.error} retry={() => query.refetch()} />
        ) : (
          query.data && (
            <Table
              data={query.data}
              page={page}
              onPage={setPage}
              columns={[
                {
                  key: "name",
                  label: "Member",
                  render: (r) => (
                    <div className="member-cell">
                      <span className="avatar pale">{String(r.name)[0]}</span>
                      <span>
                        <strong>{String(r.name)}</strong>
                        <small>{String(r.member_code)}</small>
                      </span>
                    </div>
                  ),
                },
                { key: "phone", label: "Phone" },
                {
                  key: "branch_id",
                  label: "Home branch",
                  render: (r) => rowName(branches.data, r.branch_id),
                },
                {
                  key: "status",
                  label: "Status",
                  render: (r) => <Badge value={r.status} />,
                },
                {
                  key: "created_at",
                  label: "Joined",
                  render: (r) =>
                    new Date(String(r.created_at)).toLocaleDateString(),
                },
              ]}
              actions={(r) => (
                <button className="text-button" onClick={() => setSelected(r)}>
                  View <ArrowUpRight size={14} />
                </button>
              )}
            />
          )
        )}
      </section>
      {modal === "create" && (
        <Modal title="Register a member" onClose={() => setModal(null)}>
          <Form
            fields={fields}
            submit={(d) => api("/members", send(d))}
            onDone={refresh}
          />
        </Modal>
      )}
      {modal === "import" && (
        <Modal title="Import members from CSV" onClose={() => setModal(null)}>
          <p className="modal-copy">
            UTF-8 CSV with name, phone, email columns. Up to 1,000 rows, 2 MB.
            Any invalid row prevents the entire import.
          </p>
          <ImportMembers branches={branches.data || []} onDone={refresh} />
        </Modal>
      )}
      {selected && (
        <MemberDetail
          row={selected}
          fields={fields}
          onClose={() => setSelected(null)}
          refresh={refresh}
        />
      )}
    </>
  );
}
function ImportMembers({
  branches,
  onDone,
}: {
  branches: Row[];
  onDone: () => void;
}) {
  const [error, setError] = useState<unknown>(null),
    [result, setResult] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <form
      className="form-grid"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        const f = new FormData(e.currentTarget);
        const branch = f.get("branch");
        f.delete("branch");
        try {
          const r = await api<{
            imported: number;
            errors: { row: number; message: string }[];
          }>("/members/import?branch_id=" + branch, {
            method: "POST",
            body: f,
          });
          if (r.errors.length)
            setResult(
              r.errors.map((x) => "Row " + x.row + ": " + x.message).join("\n"),
            );
          else onDone();
        } catch (e) {
          setError(e);
        } finally {
          setBusy(false);
        }
      }}
    >
      <label>
        Home branch
        <select name="branch" required>
          <option value="">Select…</option>
          {branches.map((b) => (
            <option value={b.id} key={b.id}>
              {String(b.name)}
            </option>
          ))}
        </select>
      </label>
      <label>
        CSV file
        <input type="file" name="file" accept=".csv,text/csv" required />
      </label>
      {error != null && <ErrorBox error={error} />}{" "}
      {result && (
        <pre role="alert" className="wide import-errors">
          {result}
        </pre>
      )}
      <div className="wide form-actions">
        <button className="primary" disabled={busy}>
          Validate & import
        </button>
      </div>
    </form>
  );
}
function MemberDetail({
  row,
  fields,
  onClose,
  refresh,
}: {
  row: Row;
  fields: Field[];
  onClose: () => void;
  refresh: () => void;
}) {
  const { can } = useAuth();
  const [tab, setTab] = useState("Profile");
  const [error, setError] = useState<unknown>(null);
  const ms = useQuery({
    queryKey: ["member-history", row.id],
    queryFn: () => api<Page>("/memberships?member_id=" + row.id),
    enabled: can("memberships.read"),
  });
  const invoices = useQuery({
    queryKey: ["member-payments", row.id],
    queryFn: () => api<Page>("/invoices?member_id=" + row.id),
    enabled: can("finance.read"),
  });
  return (
    <Modal
      title={String(row.name) + " · " + String(row.member_code)}
      onClose={onClose}
    >
      <div className="tabs">
        {[
          "Profile",
          "Membership history",
          ...(can("finance.read") ? ["Payment history"] : []),
        ].map((t) => (
          <button
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
            key={t}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "Profile" ? (
        <>
          {can("members.write") ? (
            <Form
              fields={[
                ...fields.filter((f) => f.name !== "branch_id"),
                {
                  name: "status",
                  label: "Profile status",
                  required: true,
                  options: ["active", "inactive", "archived"].map((v) => ({
                    value: v,
                    label: v,
                  })),
                },
              ]}
              initial={row}
              submit={(d) =>
                api("/members/" + row.id, {
                  method: "PATCH",
                  body: JSON.stringify(d),
                })
              }
              onDone={refresh}
            />
          ) : (
            <div className="detail-grid">
              {["name", "member_code", "phone", "email", "status"]
                .filter((k) => row[k] != null)
                .map((k) => (
                  <div key={k}>
                    <small>{k.replaceAll("_", " ")}</small>
                    <strong>{String(row[k])}</strong>
                  </div>
                ))}
            </div>
          )}
          {can("members.write") && (
            <form
              className="photo-upload"
              onSubmit={async (e) => {
                e.preventDefault();
                try {
                  await api("/members/" + row.id + "/photo", {
                    method: "POST",
                    body: new FormData(e.currentTarget),
                  });
                  refresh();
                } catch (e) {
                  setError(e);
                }
              }}
            >
              <label>
                Profile photo · JPEG, PNG or WebP (3 MB)
                <input
                  type="file"
                  name="file"
                  required
                  accept="image/jpeg,image/png,image/webp"
                />
              </label>
              <button>Upload photo</button>
            </form>
          )}
          {Boolean(row.has_photo) && (
            <button
              className="text-button"
              onClick={() =>
                fileRequest(
                  "/members/" + row.id + "/photo",
                  "member-photo.jpg",
                  true,
                ).catch(setError)
              }
            >
              View profile photo
            </button>
          )}
          {error != null && <ErrorBox error={error} />}
        </>
      ) : tab === "Membership history" ? (
        ms.isLoading ? (
          <Loading />
        ) : ms.error ? (
          <ErrorBox error={ms.error} />
        ) : (
          ms.data && (
            <Table
              data={ms.data.items}
              columns={[
                { key: "start_date", label: "Start" },
                { key: "end_date", label: "End (exclusive)" },
                {
                  key: "status",
                  label: "Status",
                  render: (r) => <Badge value={r.status} />,
                },
              ]}
            />
          )
        )
      ) : invoices.error ? (
        <ErrorBox error={invoices.error} />
      ) : (
        invoices.data && (
          <Table
            data={invoices.data.items}
            columns={[
              { key: "number", label: "Invoice" },
              { key: "total", label: "Total" },
              { key: "net_paid", label: "Net paid" },
              { key: "balance", label: "Balance" },
              {
                key: "status",
                label: "Status",
                render: (r) => <Badge value={r.status} />,
              },
            ]}
          />
        )
      )}
    </Modal>
  );
}
