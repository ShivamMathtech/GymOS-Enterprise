import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send, currency, localDay } from "../api";
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
import type { Page, Row } from "../types";
const planFields: Field[] = [
  { name: "name", label: "Plan name", required: true },
  {
    name: "duration_days",
    label: "Duration (days)",
    type: "number",
    required: true,
    min: 1,
    defaultValue: 30,
  },
  { name: "price", label: "Price", type: "money", required: true },
  {
    name: "discount",
    label: "Discount per membership",
    type: "money",
    required: true,
    defaultValue: "0",
  },
  {
    name: "tax_rate",
    label: "Tax %",
    type: "money",
    required: true,
    max: 100,
    defaultValue: "0",
  },
  {
    name: "all_branches",
    label: "Access all organization branches",
    type: "checkbox",
  },
  {
    name: "active",
    label: "Available for purchase",
    type: "checkbox",
    defaultValue: true,
  },
];
export default function Memberships() {
  const { can, info } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState("Memberships"),
    [page, setPage] = useState(1),
    [modal, setModal] = useState(""),
    [row, setRow] = useState<Row | null>(null);
  const members = useRows("/members"),
    plans = useRows("/plans");
  const query = useQuery({
    queryKey: ["memberships", page],
    queryFn: () => api<Page>("/memberships?page=" + page),
  });
  const close = () => {
    setModal("");
    setRow(null);
  };
  const refresh = () => {
    qc.invalidateQueries();
    close();
  };
  const planOptions = options(plans.data);
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">ACCESS & MEMBERSHIPS</div>
          <h1>Build lasting routines.</h1>
          <p>
            Plans, renewals and membership changes, with a complete history.
          </p>
        </div>
        <div className="page-actions">
          {can("plans.write") && (
            <button
              onClick={() => {
                setRow(null);
                setModal("plan");
              }}
            >
              + Create plan
            </button>
          )}
          {can("memberships.write") && (
            <button className="primary" onClick={() => setModal("assign")}>
              + Assign membership
            </button>
          )}
        </div>
      </div>
      <div className="tabs">
        {["Memberships", "Plans"].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={tab === t ? "active" : ""}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "Memberships" ? (
        <section className="card">
          {query.isLoading ? (
            <Loading />
          ) : query.error ? (
            <ErrorBox error={query.error} />
          ) : (
            query.data && (
              <Table
                data={query.data}
                page={page}
                onPage={setPage}
                columns={[
                  {
                    key: "member_id",
                    label: "Member",
                    render: (r) => rowName(members.data, r.member_id),
                  },
                  {
                    key: "plan_id",
                    label: "Plan",
                    render: (r) => rowName(plans.data, r.plan_id),
                  },
                  { key: "start_date", label: "Starts" },
                  { key: "end_date", label: "Access ends" },
                  {
                    key: "status",
                    label: "Status",
                    render: (r) => <Badge value={r.status} />,
                  },
                ]}
                actions={
                  can("memberships.write")
                    ? (r) => (
                        <>
                          <button
                            onClick={() => {
                              setRow(r);
                              setModal("renew");
                            }}
                          >
                            Renew / change plan
                          </button>
                          <button
                            onClick={() => {
                              setRow(r);
                              setModal("lifecycle");
                            }}
                          >
                            Manage
                          </button>
                          <button
                            onClick={() => {
                              setRow(r);
                              setModal("events");
                            }}
                          >
                            History
                          </button>
                        </>
                      )
                    : undefined
                }
              />
            )
          )}
        </section>
      ) : (
        <div className="plans-grid">
          {plans.error ? (
            <ErrorBox error={plans.error} />
          ) : plans.isLoading ? (
            <Loading />
          ) : !plans.data?.length ? (
            <div className="card">Create your first membership plan.</div>
          ) : (
            plans.data.map((p) => (
              <section className="card plan-card" key={p.id}>
                <div className="eyebrow">
                  {Number(p.duration_days)} DAY MEMBERSHIP
                </div>
                <h2>{String(p.name)}</h2>
                <strong>
                  {currency(p.price, info?.organization.currency)}
                </strong>
                <p>
                  Discount {currency(p.discount, info?.organization.currency)} ·
                  Tax {String(p.tax_rate)}%
                </p>
                <p>{p.all_branches ? "All branches" : "Home branch only"}</p>
                <Badge value={p.active ? "active" : "inactive"} />
                {can("plans.write") && (
                  <button
                    onClick={() => {
                      setRow(p);
                      setModal("plan");
                    }}
                  >
                    Edit plan
                  </button>
                )}
              </section>
            ))
          )}
        </div>
      )}
      {modal === "plan" && (
        <Modal
          title={row ? "Edit membership plan" : "Create membership plan"}
          onClose={close}
        >
          <Form
            fields={planFields}
            initial={row || {}}
            submit={(d) =>
              api("/plans" + (row ? "/" + row.id : ""), {
                method: row ? "PUT" : "POST",
                body: JSON.stringify(d),
              })
            }
            onDone={refresh}
          />
        </Modal>
      )}
      {modal === "assign" && (
        <Modal title="Assign membership" onClose={close}>
          <p className="modal-copy">
            Creates an invoice. Access activates when the invoice is paid in
            full. End dates are exclusive.
          </p>
          <Form
            fields={[
              {
                name: "member_id",
                label: "Member",
                required: true,
                options: options(members.data),
              },
              {
                name: "plan_id",
                label: "Plan",
                required: true,
                options: planOptions,
              },
              {
                name: "start_date",
                label: "Start date",
                type: "date",
                required: true,
                defaultValue: localDay(),
              },
            ]}
            submit={(d, requestKey) =>
              api("/memberships", send({ ...d, request_key: requestKey }))
            }
            onDone={refresh}
          />
        </Modal>
      )}
      {modal === "renew" && row && (
        <Modal title="Renew or change plan" onClose={close}>
          <p className="modal-copy">
            The new plan starts after the latest non-cancelled membership ends,
            or today if expired. Upgrade and downgrade take effect at renewal;
            no automatic prorated credit.
          </p>
          <Form
            fields={[
              {
                name: "plan_id",
                label: "Renewal plan",
                required: true,
                options: planOptions,
                defaultValue: row.plan_id,
              },
            ]}
            submit={(d, requestKey) =>
              api(
                "/memberships/" + row.id + "/renew",
                send({ ...d, request_key: requestKey }),
              )
            }
            onDone={refresh}
          />
        </Modal>
      )}
      {modal === "lifecycle" && row && (
        <Modal title="Manage membership" onClose={close}>
          <p className="modal-copy">
            Freeze starts today and extends access by the selected days.
            Cancellation stops access; refunds are recorded separately in
            Billing.
          </p>
          <Form
            fields={[
              {
                name: "action",
                label: "Action",
                required: true,
                options: ["freeze", "extend", "cancel"].map((v) => ({
                  value: v,
                  label: v,
                })),
              },
              {
                name: "days",
                label: "Days (0 for cancellation)",
                type: "number",
                defaultValue: 0,
                min: 0,
                max: 366,
              },
              {
                name: "reason",
                label: "Reason",
                required: true,
                type: "textarea",
              },
            ]}
            submit={(d) =>
              api("/memberships/" + row.id + "/lifecycle", send(d))
            }
            onDone={refresh}
          />
        </Modal>
      )}
      {modal === "events" && row && <History id={row.id} onClose={close} />}
    </>
  );
}
function History({ id, onClose }: { id: string; onClose: () => void }) {
  const q = useQuery({
    queryKey: ["events", id],
    queryFn: () => api<Row[]>("/memberships/" + id + "/events"),
  });
  return (
    <Modal title="Membership audit history" onClose={onClose}>
      {q.isLoading ? (
        <Loading />
      ) : q.error ? (
        <ErrorBox error={q.error} />
      ) : (
        q.data && (
          <Table
            data={q.data}
            columns={[
              {
                key: "created_at",
                label: "Time",
                render: (r) => new Date(String(r.created_at)).toLocaleString(),
              },
              { key: "action", label: "Event" },
              {
                key: "details",
                label: "Details",
                render: (r) => JSON.stringify(r.details),
              },
            ]}
          />
        )
      )}
    </Modal>
  );
}
