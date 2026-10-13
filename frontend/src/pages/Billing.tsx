import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send, currency, fileRequest } from "../api";
import { useAuth } from "../auth";
import { useRows, options, rowName } from "../hooks";
import { Table, Modal, Form, Loading, ErrorBox, Badge } from "../components/ui";
import { ResourceModule } from "./Resources";
import type { Page, Row, Invoice } from "../types";
export default function Billing() {
  const { can, info } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1),
    [modal, setModal] = useState(""),
    [selected, setSelected] = useState<Row | null>(null),
    [tab, setTab] = useState("Invoices");
  const members = useRows("/members");
  const query = useQuery({
    queryKey: ["invoices", page],
    queryFn: () => api<Page<Invoice>>("/invoices?page=" + page),
  });
  const refresh = () => {
    qc.invalidateQueries();
    setModal("");
  };
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">FINANCIAL OPERATIONS</div>
          <h1>Every payment, accounted for.</h1>
          <p>Invoices, collections and refunds with an immutable history.</p>
        </div>
        {can("finance.write") && (
          <button className="primary" onClick={() => setModal("invoice")}>
            + Create invoice
          </button>
        )}
      </div>
      <div className="tabs">
        {["Invoices", ...(can("finance.write") ? ["Expenses"] : [])].map(
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
      {tab === "Expenses" ? (
        <ResourceModule group="expenses" />
      ) : (
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
                  { key: "number", label: "Invoice" },
                  {
                    key: "member_id",
                    label: "Member",
                    render: (r) => rowName(members.data, r.member_id),
                  },
                  {
                    key: "total",
                    label: "Total",
                    render: (r) => currency(r.total, String(r.currency)),
                  },
                  {
                    key: "net_paid",
                    label: "Net paid",
                    render: (r) => currency(r.net_paid, String(r.currency)),
                  },
                  {
                    key: "balance",
                    label: "Due",
                    render: (r) => currency(r.balance, String(r.currency)),
                  },
                  {
                    key: "status",
                    label: "Status",
                    render: (r) => <Badge value={r.status} />,
                  },
                ]}
                actions={(r) => (
                  <>
                    <button
                      onClick={() => {
                        setSelected(r);
                        setModal("detail");
                      }}
                    >
                      Details
                    </button>
                    {Number(r.balance) > 0 &&
                      (can("finance.write") || can("finance.collect")) && (
                        <button
                          onClick={() => {
                            setSelected(r);
                            setModal("payment");
                          }}
                        >
                          Record payment
                        </button>
                      )}
                  </>
                )}
              />
            )
          )}
        </section>
      )}
      {modal === "invoice" && (
        <Modal title="Create invoice" onClose={() => setModal("")}>
          <p className="modal-copy">
            Membership assignment creates its own invoice. Use this form for a
            service or product. All amounts use {info?.organization.currency}.
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
                name: "description",
                label: "Line description",
                required: true,
              },
              {
                name: "quantity",
                label: "Quantity",
                type: "number",
                required: true,
                defaultValue: 1,
                min: 1,
              },
              {
                name: "unit_price",
                label: "Unit price",
                type: "money",
                required: true,
              },
              {
                name: "discount",
                label: "Line discount",
                type: "money",
                required: true,
                defaultValue: 0,
              },
              {
                name: "tax_rate",
                label: "Tax %",
                type: "money",
                required: true,
                defaultValue: 0,
                max: 100,
              },
            ]}
            submit={({ member_id, ...line }) =>
              api("/invoices", send({ member_id, lines: [line] }))
            }
            onDone={refresh}
          />
        </Modal>
      )}
      {modal === "payment" && selected && (
        <Modal
          title={"Record payment · " + selected.number}
          onClose={() => setModal("")}
        >
          <p className="modal-copy">
            Record money already received. This action does not charge a card or
            collect a UPI payment.
          </p>
          <Form
            fields={[
              {
                name: "amount",
                label: "Amount received",
                type: "money",
                required: true,
                defaultValue: selected.balance,
                max: Number(selected.balance),
              },
              {
                name: "method",
                label: "Method",
                required: true,
                options: ["cash", "upi", "card", "bank_transfer", "other"].map(
                  (v) => ({ value: v, label: v.replaceAll("_", " ") }),
                ),
              },
              { name: "reference", label: "Payment reference" },
            ]}
            submit={(d, requestKey) =>
              api(
                "/payments",
                send({
                  ...d,
                  invoice_id: selected.id,
                  idempotency_key: requestKey,
                }),
              )
            }
            onDone={refresh}
          />
        </Modal>
      )}
      {modal === "detail" && selected && (
        <InvoiceDetail id={selected.id} onClose={() => setModal("")} />
      )}
    </>
  );
}
function InvoiceDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [refund, setRefund] = useState<Row | null>(null),
    [cancel, setCancel] = useState(false),
    [error, setError] = useState<unknown>(null);
  const query = useQuery({
    queryKey: ["invoice", id],
    queryFn: () =>
      api<Invoice & { items: Row[]; payments: Row[]; refunds: Row[] }>(
        "/invoices/" + id,
      ),
  });
  const d = query.data;
  const refresh = () => {
    qc.invalidateQueries();
    setRefund(null);
    setCancel(false);
  };
  return (
    <Modal
      title={d ? "Invoice " + d.number : "Invoice details"}
      onClose={onClose}
    >
      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <ErrorBox error={query.error} />
      ) : (
        d && (
          <>
            <div className="detail-grid">
              <div>
                <small>Invoice total</small>
                <strong>{currency(d.total, d.currency)}</strong>
              </div>
              <div>
                <small>Outstanding</small>
                <strong>{currency(d.balance, d.currency)}</strong>
              </div>
              <Badge value={d.status} />
            </div>
            <h3>Line items</h3>
            <Table
              data={d.items}
              columns={[
                { key: "description", label: "Description" },
                { key: "quantity", label: "Qty" },
                { key: "unit_price", label: "Unit price" },
                { key: "discount", label: "Discount" },
                { key: "tax_amount", label: "Tax" },
                { key: "total", label: "Total" },
              ]}
            />
            <h3>Payments & receipts</h3>
            <Table
              data={d.payments}
              columns={[
                {
                  key: "created_at",
                  label: "Recorded",
                  render: (r) =>
                    new Date(String(r.created_at)).toLocaleString(),
                },
                { key: "amount", label: "Amount" },
                { key: "method", label: "Method" },
                { key: "reference", label: "Reference" },
              ]}
              actions={(r) => (
                <>
                  <button
                    onClick={() =>
                      fileRequest(
                        "/payments/" + r.id + "/receipt",
                        "receipt.html",
                        true,
                      ).catch(setError)
                    }
                  >
                    Receipt
                  </button>
                  {can("finance.write") && (
                    <button onClick={() => setRefund(r)}>Refund</button>
                  )}
                </>
              )}
            />
            <h3>Refund history</h3>
            <Table
              data={d.refunds}
              columns={[
                { key: "amount", label: "Amount" },
                { key: "reason", label: "Reason" },
                {
                  key: "created_at",
                  label: "Recorded",
                  render: (r) =>
                    new Date(String(r.created_at)).toLocaleString(),
                },
              ]}
            />
            {error != null && <ErrorBox error={error} />}{" "}
            {refund && (
              <section className="inline-form">
                <h3>Record refund</h3>
                <p>
                  Record money returned outside GymOS. Refunds reduce net
                  payment and may suspend membership access.
                </p>
                <Form
                  fields={[
                    {
                      name: "amount",
                      label: "Refund amount",
                      type: "money",
                      required: true,
                      max: Number(refund.amount),
                    },
                    {
                      name: "reason",
                      label: "Reason",
                      type: "textarea",
                      required: true,
                    },
                  ]}
                  submit={(v, requestKey) =>
                    api(
                      "/refunds",
                      send({
                        ...v,
                        payment_id: refund.id,
                        idempotency_key: requestKey,
                      }),
                    )
                  }
                  onDone={refresh}
                />
              </section>
            )}
            {can("finance.write") && d.status !== "cancelled" && (
              <button onClick={() => setCancel(!cancel)}>Cancel invoice</button>
            )}
            {cancel && (
              <Form
                fields={[
                  {
                    name: "reason",
                    label: "Cancellation reason",
                    required: true,
                  },
                ]}
                submit={(v) => api("/invoices/" + id + "/cancel", send(v))}
                onDone={refresh}
              />
            )}
          </>
        )
      )}
    </Modal>
  );
}
