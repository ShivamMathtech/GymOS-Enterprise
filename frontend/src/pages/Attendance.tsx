import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { api, send } from "../api";
import { useAuth } from "../auth";
import { useRows, options, rowName } from "../hooks";
import {
  Table,
  Modal,
  Form,
  Loading,
  ErrorBox,
  Badge,
  Confirm,
} from "../components/ui";
import type { Page, Row } from "../types";
export default function AttendancePage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1),
    [modal, setModal] = useState(""),
    [row, setRow] = useState<Row | null>(null),
    [qr, setQr] = useState<{ token: string; expires_at: string } | null>(null);
  const members = useRows("/members"),
    branches = useRows("/branches");
  const query = useQuery({
    queryKey: ["attendance", page],
    queryFn: () => api<Page>("/attendance?page=" + page),
    refetchInterval: 30000,
  });
  const refresh = () => {
    qc.invalidateQueries();
    setModal("");
    setRow(null);
  };
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">FRONT DESK</div>
          <h1>A smooth start to every visit.</h1>
          <p>Membership eligibility is checked before every entry.</p>
        </div>
        {can("attendance.write") && (
          <div className="page-actions">
            <button onClick={() => setModal("generate")}>
              Generate member QR
            </button>
            <button onClick={() => setModal("qr")}>QR check-in</button>
            <button className="primary" onClick={() => setModal("manual")}>
              + Check in member
            </button>
          </div>
        )}
      </div>
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
                  key: "branch_id",
                  label: "Branch",
                  render: (r) => rowName(branches.data, r.branch_id),
                },
                {
                  key: "checked_in_at",
                  label: "Check-in",
                  render: (r) =>
                    new Date(String(r.checked_in_at)).toLocaleString(),
                },
                {
                  key: "checked_out_at",
                  label: "Check-out",
                  render: (r) =>
                    r.checked_out_at ? (
                      new Date(String(r.checked_out_at)).toLocaleString()
                    ) : (
                      <Badge value="active" />
                    ),
                },
                { key: "source", label: "Source" },
              ]}
              actions={
                can("attendance.write")
                  ? (r) => (
                      <>
                        {!r.checked_out_at && (
                          <button
                            onClick={() => {
                              setRow(r);
                              setModal("checkout");
                            }}
                          >
                            Check out
                          </button>
                        )}
                        {can("attendance.correct") && (
                          <button
                            onClick={() => {
                              setRow(r);
                              setModal("correct");
                            }}
                          >
                            Correct
                          </button>
                        )}
                      </>
                    )
                  : undefined
              }
            />
          )
        )}
      </section>
      {["manual", "qr", "generate"].includes(modal) && (
        <Modal
          title={
            modal === "manual"
              ? "Check in member"
              : modal === "qr"
                ? "Validate QR check-in"
                : "Generate member QR"
          }
          onClose={() => setModal("")}
        >
          <p className="modal-copy">
            QR tokens expire after two minutes and can be used once. Scan with a
            keyboard scanner or paste the token below.
          </p>
          <Form
            fields={
              modal === "generate"
                ? [
                    {
                      name: "member_id",
                      label: "Member",
                      required: true,
                      options: options(members.data),
                    },
                  ]
                : [
                    {
                      name: modal === "qr" ? "token" : "member_id",
                      label: modal === "qr" ? "Scanned QR token" : "Member",
                      required: true,
                      ...(modal === "qr"
                        ? {}
                        : { options: options(members.data) }),
                    },
                    {
                      name: "branch_id",
                      label: "Check-in branch",
                      required: true,
                      options: options(branches.data),
                    },
                  ]
            }
            submit={async (d) => {
              if (modal === "generate") {
                setQr(await api("/attendance/qr/" + d.member_id, send({})));
                setModal("");
              } else
                await api(
                  modal === "qr"
                    ? "/attendance/qr-check-in"
                    : "/attendance/check-in",
                  send(d),
                );
            }}
            onDone={modal === "generate" ? undefined : refresh}
          />
        </Modal>
      )}
      {qr && (
        <Modal title="One-time member QR" onClose={() => setQr(null)}>
          <div className="qr-card">
            <QRCodeSVG value={qr.token} size={210} />
            <p>Valid until {new Date(qr.expires_at).toLocaleTimeString()}</p>
            <code>{qr.token}</code>
          </div>
        </Modal>
      )}
      {modal === "checkout" && row && (
        <Confirm
          title="Check out member"
          message="Record the current time as this visit’s checkout?"
          onClose={() => setModal("")}
          onConfirm={async () => {
            await api("/attendance/" + row.id + "/check-out", send({}));
            refresh();
          }}
        />
      )}
      {modal === "correct" && row && (
        <Modal title="Correct attendance" onClose={() => setModal("")}>
          <Form
            fields={[
              {
                name: "checked_in_at",
                label: "Check-in (local)",
                type: "datetime-local",
                required: true,
              },
              {
                name: "checked_out_at",
                label: "Check-out (local)",
                type: "datetime-local",
              },
              {
                name: "reason",
                label: "Correction reason",
                required: true,
                type: "textarea",
              },
            ]}
            submit={(d) =>
              api("/attendance/" + row.id, {
                method: "PATCH",
                body: JSON.stringify({
                  ...d,
                  checked_in_at: new Date(
                    String(d.checked_in_at),
                  ).toISOString(),
                  checked_out_at: d.checked_out_at
                    ? new Date(String(d.checked_out_at)).toISOString()
                    : null,
                }),
              })
            }
            onDone={refresh}
          />
        </Modal>
      )}
    </>
  );
}
