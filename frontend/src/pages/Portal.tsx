import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { api, send, localDay, currency } from "../api";
import { useAuth } from "../auth";
import { options, rowName } from "../hooks";
import { Table, Modal, Form, Loading, ErrorBox, Badge } from "../components/ui";
import type { Row } from "../types";
type PortalData = {
  member: Row;
  memberships: Row[];
  invoices: Row[];
  attendance: Row[];
  sessions: Row[];
  workouts: Row[];
  workout_exercises: Row[];
  progress: Row[];
  exercise_library: Row[];
};
export default function Portal() {
  const { info } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState("Membership"),
    [log, setLog] = useState(false),
    [qr, setQr] = useState<{ token: string; expires_at: string } | null>(null),
    [error, setError] = useState<unknown>(null);
  const q = useQuery({
    queryKey: ["portal"],
    queryFn: () => api<PortalData>("/portal"),
  });
  const d = q.data;
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  if (!d) return null;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">YOUR FITNESS JOURNEY</div>
          <h1>Keep showing up, {info?.user.name.split(" ")[0]}.</h1>
          <p>
            {String(d.member.member_code)} · {String(d.member.name)}
          </p>
        </div>
        <div className="page-actions">
          <button onClick={() => setLog(true)}>Log a workout</button>
          <button
            className="primary"
            onClick={() =>
              api<{ token: string; expires_at: string }>(
                "/attendance/qr/" + d.member.id,
                send({}),
              )
                .then(setQr)
                .catch(setError)
            }
          >
            My check-in QR
          </button>
        </div>
      </div>
      {error != null && <ErrorBox error={error} />}
      <div className="tabs">
        {[
          "Membership",
          "Invoices",
          "Visits",
          "Sessions",
          "Workouts",
          "Progress",
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
      <section className="card">
        {tab === "Membership" ? (
          <Table
            data={d.memberships}
            columns={[
              { key: "start_date", label: "From" },
              { key: "end_date", label: "Access ends" },
              {
                key: "status",
                label: "Status",
                render: (r) => <Badge value={r.status} />,
              },
            ]}
          />
        ) : tab === "Invoices" ? (
          <Table
            data={d.invoices}
            columns={[
              { key: "number", label: "Invoice" },
              {
                key: "total",
                label: "Total",
                render: (r) => currency(r.total, info?.organization.currency),
              },
              {
                key: "balance",
                label: "Balance",
                render: (r) => currency(r.balance, info?.organization.currency),
              },
              {
                key: "status",
                label: "Status",
                render: (r) => <Badge value={r.status} />,
              },
            ]}
          />
        ) : tab === "Visits" ? (
          <Table
            data={d.attendance}
            columns={[
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
                  r.checked_out_at
                    ? new Date(String(r.checked_out_at)).toLocaleString()
                    : "In gym",
              },
            ]}
          />
        ) : tab === "Sessions" ? (
          <Table
            data={d.sessions}
            columns={[
              {
                key: "starts_at",
                label: "Starts",
                render: (r) => new Date(String(r.starts_at)).toLocaleString(),
              },
              {
                key: "ends_at",
                label: "Ends",
                render: (r) => new Date(String(r.ends_at)).toLocaleString(),
              },
              {
                key: "state",
                label: "Status",
                render: (r) => <Badge value={r.state} />,
              },
            ]}
          />
        ) : tab === "Progress" ? (
          <Table
            data={d.progress}
            columns={[
              { key: "measured_on", label: "Measured on" },
              { key: "weight_kg", label: "Body weight (kg)" },
              { key: "waist_cm", label: "Waist (cm)" },
            ]}
          />
        ) : (
          <>
            <Table
              data={d.workouts}
              columns={[
                { key: "name", label: "Plan" },
                { key: "description", label: "Instructions" },
                { key: "scheduled_date", label: "Schedule" },
              ]}
            />
            <h3>Assigned exercises</h3>
            <Table
              data={d.workout_exercises}
              columns={[
                {
                  key: "workout_plan_id",
                  label: "Plan",
                  render: (r) => rowName(d.workouts, r.workout_plan_id),
                },
                {
                  key: "exercise_id",
                  label: "Exercise",
                  render: (r) => rowName(d.exercise_library, r.exercise_id),
                },
                { key: "sets", label: "Sets" },
                { key: "repetitions", label: "Repetitions" },
                { key: "weight_kg", label: "Weight (kg)" },
                { key: "duration_seconds", label: "Duration (s)" },
              ]}
            />
          </>
        )}
      </section>
      <p className="footnote">
        The portal displays your latest 100 records per category. Contact
        reception for older records or schedule changes.
      </p>
      {qr && (
        <Modal title="Your one-time check-in QR" onClose={() => setQr(null)}>
          <div className="qr-card">
            <QRCodeSVG value={qr.token} size={210} />
            <p>Expires {new Date(qr.expires_at).toLocaleTimeString()}</p>
            <code>{qr.token}</code>
          </div>
        </Modal>
      )}
      {log && (
        <Modal title="Log a workout" onClose={() => setLog(false)}>
          <Form
            fields={[
              {
                name: "exercise_id",
                label: "Exercise",
                required: true,
                options: options(d.exercise_library),
              },
              {
                name: "performed_on",
                label: "Workout date",
                type: "date",
                required: true,
                defaultValue: localDay(),
              },
              {
                name: "sets",
                label: "Sets",
                type: "number",
                min: 1,
                required: true,
              },
              {
                name: "repetitions",
                label: "Repetitions",
                type: "number",
                min: 1,
                required: true,
              },
              {
                name: "weight_kg",
                label: "Weight (kg)",
                type: "money",
                required: true,
                defaultValue: 0,
              },
              {
                name: "duration_seconds",
                label: "Duration (seconds)",
                type: "number",
                required: true,
                defaultValue: 0,
              },
            ]}
            submit={(v) =>
              api(
                "/portal/workout-logs",
                send({ ...v, member_id: d.member.id }),
              )
            }
            onDone={() => {
              setLog(false);
              qc.invalidateQueries();
            }}
          />
        </Modal>
      )}
    </>
  );
}
