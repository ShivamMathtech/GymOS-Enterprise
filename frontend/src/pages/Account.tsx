import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth } from "../auth";
import { Table, Loading, ErrorBox, Confirm } from "../components/ui";
import type { Row } from "../types";
export default function Account() {
  const { info } = useAuth();
  const qc = useQueryClient();
  const [id, setId] = useState("");
  const q = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api<Row[]>("/auth/sessions"),
  });
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">ACCOUNT SECURITY</div>
          <h1>Your signed-in devices.</h1>
          <p>
            {info?.user.email} · Revoke a session to require a fresh sign-in.
          </p>
        </div>
      </div>
      <section className="card">
        {q.isLoading ? (
          <Loading />
        ) : q.error ? (
          <ErrorBox error={q.error} />
        ) : (
          q.data && (
            <Table
              data={q.data}
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
                <button onClick={() => setId(r.id)}>Revoke</button>
              )}
            />
          )
        )}
      </section>
      {id && (
        <Confirm
          title="Revoke this session?"
          message="The device will need to sign in again. Revoking your current session will also sign you out on your next request."
          onClose={() => setId("")}
          onConfirm={async () => {
            await api("/auth/sessions/" + id, { method: "DELETE" });
            qc.invalidateQueries();
          }}
        />
      )}
    </>
  );
}
