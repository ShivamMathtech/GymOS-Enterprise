import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send } from "../api";
import { useAuth } from "../auth";
import { useRows, options } from "../hooks";
import {
  Table,
  Modal,
  Form,
  Loading,
  ErrorBox,
  Confirm,
  type Field,
} from "../components/ui";
import type { Page, Row } from "../types";
const branchFields: Field[] = [
  { name: "name", label: "Branch name", required: true },
  { name: "address", label: "Address" },
  {
    name: "timezone",
    label: "IANA time zone",
    required: true,
    defaultValue: "Asia/Kolkata",
  },
  {
    name: "opens",
    label: "Opens",
    type: "time",
    required: true,
    defaultValue: "05:00",
  },
  {
    name: "closes",
    label: "Closes",
    type: "time",
    required: true,
    defaultValue: "23:00",
  },
  {
    name: "grace_days",
    label: "Membership grace days",
    type: "number",
    required: true,
    min: 0,
    max: 30,
    defaultValue: 0,
  },
  { name: "active", label: "Active", type: "checkbox", defaultValue: true },
];
export function SettingsPage() {
  const { info, can } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState("Branches"),
    [modal, setModal] = useState(""),
    [selected, setSelected] = useState<Row | null>(null),
    [notice, setNotice] = useState(""),
    [error, setError] = useState<unknown>(null),
    [revoke, setRevoke] = useState("");
  const branches = useRows("/branches"),
    members = useRows("/members"),
    staff = useRows("/staff", can("staff.manage"));
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api<Row[]>("/auth/sessions"),
  });
  const permissions = useQuery({
    queryKey: ["permissions"],
    queryFn: () => api<Record<string, string[]>>("/staff/permissions/roles"),
    enabled: can("staff.manage"),
  });
  const refresh = () => {
    qc.invalidateQueries();
    setModal("");
  };
  const roles = [
    "Gym Owner",
    "Manager",
    "Receptionist",
    "Trainer",
    "Accountant",
    "Member",
  ];
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">WORKSPACE ADMINISTRATION</div>
          <h1>Make GymOS yours.</h1>
          <p>Branches, team access and organization settings.</p>
        </div>
        {tab === "Branches" ? (
          <button
            className="primary"
            onClick={() => {
              setSelected(null);
              setModal("branch");
            }}
          >
            + Add branch
          </button>
        ) : tab === "Team" && can("staff.manage") ? (
          <button
            className="primary"
            onClick={() => {
              setSelected(null);
              setModal("invite");
            }}
          >
            + Invite team member
          </button>
        ) : null}
      </div>
      <div className="tabs">
        {["Branches", "Organization", "Team", "Permissions", "Sessions"].map(
          (t) => (
            <button
              className={tab === t ? "active" : ""}
              onClick={() => setTab(t)}
              key={t}
            >
              {t}
            </button>
          ),
        )}
      </div>
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      {error != null && <ErrorBox error={error} />}
      <section className="card">
        {tab === "Branches" ? (
          branches.error ? (
            <ErrorBox error={branches.error} />
          ) : (
            branches.data && (
              <Table
                data={branches.data}
                columns={[
                  { key: "name", label: "Branch" },
                  { key: "timezone", label: "Time zone" },
                  { key: "opens", label: "Opens" },
                  { key: "closes", label: "Closes" },
                  { key: "grace_days", label: "Grace days" },
                  { key: "active", label: "Active" },
                ]}
                actions={(r) => (
                  <button
                    onClick={() => {
                      setSelected(r);
                      setModal("branch");
                    }}
                  >
                    Edit
                  </button>
                )}
              />
            )
          )
        ) : tab === "Organization" ? (
          <Form
            fields={[
              { name: "name", label: "Organization name", required: true },
              {
                name: "timezone",
                label: "Organization time zone",
                required: true,
              },
              {
                name: "invoice_prefix",
                label: "Invoice prefix",
                required: true,
                hint: "1–12 uppercase letters, digits or hyphens.",
              },
            ]}
            initial={info?.organization}
            submit={(d) =>
              api("/organization", { method: "PUT", body: JSON.stringify(d) })
            }
            onDone={() => {
              setNotice(
                "Organization saved. Sign in again to refresh the workspace label.",
              );
              qc.invalidateQueries();
            }}
          />
        ) : tab === "Team" ? (
          staff.error ? (
            <ErrorBox error={staff.error} />
          ) : (
            staff.data && (
              <Table
                data={staff.data}
                columns={[
                  { key: "name", label: "Name" },
                  { key: "email", label: "Email" },
                  { key: "role", label: "Role" },
                  { key: "active", label: "Active" },
                  {
                    key: "id",
                    label: "Account ID",
                    render: (r) => <code className="small-code">{r.id}</code>,
                  },
                ]}
                actions={(r) => (
                  <button
                    disabled={r.id === info?.user.id || r.role === "Member"}
                    onClick={() => {
                      setSelected(r);
                      setModal("staff");
                    }}
                  >
                    Edit access
                  </button>
                )}
              />
            )
          )
        ) : tab === "Permissions" ? (
          permissions.error ? (
            <ErrorBox error={permissions.error} />
          ) : (
            <div className="permission-grid">
              {Object.entries(permissions.data || {}).map(([role, ps]) => (
                <section key={role}>
                  <h3>{role}</h3>
                  <p>{ps.join(", ")}</p>
                </section>
              ))}
            </div>
          )
        ) : sessions.error ? (
          <ErrorBox error={sessions.error} />
        ) : (
          sessions.data && (
            <Table
              data={sessions.data}
              columns={[
                { key: "device", label: "Device" },
                {
                  key: "created_at",
                  label: "Started",
                  render: (r) =>
                    new Date(String(r.created_at)).toLocaleString(),
                },
                {
                  key: "expires_at",
                  label: "Expires",
                  render: (r) =>
                    new Date(String(r.expires_at)).toLocaleString(),
                },
              ]}
              actions={(r) => (
                <button onClick={() => setRevoke(r.id)}>Revoke</button>
              )}
            />
          )
        )}
      </section>
      {modal === "branch" && (
        <Modal
          title={selected ? "Edit branch" : "Create branch"}
          onClose={() => setModal("")}
        >
          <p className="modal-copy">
            Equal opening and closing times mean 24-hour access. Overnight
            working hours are supported.
          </p>
          <Form
            fields={branchFields}
            initial={selected || {}}
            submit={(d) =>
              api("/branches" + (selected ? "/" + selected.id : ""), {
                method: selected ? "PUT" : "POST",
                body: JSON.stringify(d),
              })
            }
            onDone={refresh}
          />
        </Modal>
      )}
      {modal === "invite" && (
        <Modal
          title="Invite a staff member or member"
          onClose={() => setModal("")}
        >
          <Form
            fields={[
              { name: "name", label: "Name", required: true },
              { name: "email", label: "Email", type: "email", required: true },
              {
                name: "role",
                label: "Role",
                required: true,
                options: roles.map((v) => ({ value: v, label: v })),
              },
              {
                name: "branch_id",
                label: "Assigned branch",
                options: options(branches.data),
                hint: "Required for staff other than owners.",
              },
              {
                name: "member_id",
                label: "Member profile (Member role only)",
                options: options(members.data),
              },
            ]}
            submit={async (d) => {
              const { branch_id, ...rest } = d;
              const r = await api<{
                activation_url: string | null;
                email_delivered: boolean;
              }>(
                "/staff/invite",
                send({ ...rest, branch_ids: branch_id ? [branch_id] : [] }),
              );
              setNotice(
                r.activation_url
                  ? "Invitation created. Share this one-time activation link securely: " +
                      r.activation_url
                  : "Invitation email sent.",
              );
            }}
            onDone={refresh}
          />
        </Modal>
      )}
      {modal === "staff" && selected && (
        <Modal title="Edit staff access" onClose={() => setModal("")}>
          <Form
            fields={[
              {
                name: "role",
                label: "Role",
                required: true,
                options: roles
                  .filter((v) => v !== "Member")
                  .map((v) => ({ value: v, label: v })),
              },
              { name: "active", label: "Active", type: "checkbox" },
              {
                name: "branch_ids",
                label: "Assigned branches",
                type: "multiselect",
                options: options(branches.data),
                hint: "Hold Ctrl or Cmd to select multiple branches.",
              },
            ]}
            initial={{
              ...selected,
              branch_ids: Array.isArray(selected.branch_ids)
                ? selected.branch_ids
                : "",
            }}
            submit={(d) =>
              api("/staff/" + selected.id, {
                method: "PUT",
                body: JSON.stringify({
                  ...d,
                  branch_ids: d.branch_ids,
                }),
              })
            }
            onDone={refresh}
          />
        </Modal>
      )}
      {revoke && (
        <Confirm
          title="Revoke session"
          message="This device will need to sign in again. If this is your current session, your next request will require sign-in."
          onClose={() => setRevoke("")}
          onConfirm={async () => {
            await api("/auth/sessions/" + revoke, { method: "DELETE" });
            qc.invalidateQueries();
          }}
        />
      )}
    </>
  );
}
export function Notifications() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1),
    [error, setError] = useState<unknown>(null);
  const q = useQuery({
    queryKey: ["notifications", page],
    queryFn: () => api<Page>("/notifications?page=" + page),
    refetchInterval: 60000,
  });
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">STAY INFORMED</div>
          <h1>Your notifications.</h1>
          <p>Renewals, receipts and the reminders that matter.</p>
        </div>
      </div>
      {error != null && <ErrorBox error={error} />}
      <section className="card">
        {q.isLoading ? (
          <Loading />
        ) : q.error ? (
          <ErrorBox error={q.error} />
        ) : (
          q.data && (
            <Table
              data={q.data}
              page={page}
              onPage={setPage}
              columns={[
                { key: "title", label: "Notification" },
                { key: "body", label: "Details" },
                {
                  key: "created_at",
                  label: "Received",
                  render: (r) =>
                    new Date(String(r.created_at)).toLocaleString(),
                },
              ]}
              actions={(r) =>
                r.read_at ? (
                  <span className="muted-text">Read</span>
                ) : (
                  <button
                    onClick={() =>
                      api("/notifications/" + r.id + "/read", send({}))
                        .then(() => qc.invalidateQueries())
                        .catch(setError)
                    }
                  >
                    Mark read
                  </button>
                )
              }
            />
          )
        )}
      </section>
    </>
  );
}
export function Audit() {
  const [page, setPage] = useState(1),
    [action, setAction] = useState("");
  const q = useQuery({
    queryKey: ["audit", page, action],
    queryFn: () =>
      api<Page>(
        "/audit?page=" + page + "&action=" + encodeURIComponent(action),
      ),
  });
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">ACCOUNTABILITY</div>
          <h1>A clear trail of changes.</h1>
          <p>Security and business events, recorded as they happen.</p>
        </div>
      </div>
      <section className="card">
        <div className="toolbar">
          <input
            aria-label="Filter audit action"
            placeholder="Filter action…"
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(1);
            }}
          />
        </div>
        {q.isLoading ? (
          <Loading />
        ) : q.error ? (
          <ErrorBox error={q.error} />
        ) : (
          q.data && (
            <Table
              data={q.data}
              page={page}
              onPage={setPage}
              columns={[
                {
                  key: "created_at",
                  label: "Time",
                  render: (r) =>
                    new Date(String(r.created_at)).toLocaleString(),
                },
                { key: "action", label: "Action" },
                {
                  key: "actor_id",
                  label: "Actor",
                  render: (r) => String(r.actor_id ?? "System").slice(0, 8),
                },
                {
                  key: "entity_id",
                  label: "Entity",
                  render: (r) => String(r.entity_id).slice(0, 8),
                },
                {
                  key: "details",
                  label: "Details",
                  render: (r) => JSON.stringify(r.details),
                },
              ]}
            />
          )
        )}
      </section>
    </>
  );
}
