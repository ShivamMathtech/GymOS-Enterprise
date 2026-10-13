import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Users,
  UserCheck,
  IndianRupee,
  ScanLine,
  ArrowUpRight,
  Download,
  CalendarDays,
  Clock3,
  Package,
} from "lucide-react";
import { api, currency, fileRequest } from "../api";
import { useAuth } from "../auth";
import { Loading, ErrorBox, Empty } from "../components/ui";
import type { Dashboard as Data, Branch } from "../types";
export default function Dashboard({ reports = false }: { reports?: boolean }) {
  const { info, can } = useAuth();
  const [branch, setBranch] = useState(""),
    [from, setFrom] = useState(""),
    [to, setTo] = useState(""),
    [error, setError] = useState<unknown>(null);
  const { data: branches } = useQuery({
    queryKey: ["branches"],
    queryFn: () => api<Branch[]>("/branches"),
  });
  const params = new URLSearchParams();
  if (branch) params.set("branch_id", branch);
  if (from) params.set("from_date", from);
  if (to) params.set("to_date", to);
  const query = useQuery({
    queryKey: ["dashboard", branch, from, to],
    queryFn: () => api<Data>("/reports/dashboard?" + params),
  });
  const data = query.data;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">YOUR CLUB, AT A GLANCE</div>
          <h1>
            {reports
              ? "The numbers behind your progress."
              : "Good to see you, " + info?.user.name.split(" ")[0] + "."}
          </h1>
          <p>
            {reports
              ? "Track collections, participation and membership health."
              : "Here’s how your club is moving today."}
          </p>
        </div>
        <div className="page-actions">
          <button
            onClick={() =>
              fileRequest(
                "/reports/export?" + params,
                "gymos-report.csv",
              ).catch(setError)
            }
          >
            <Download size={16} />
            Export report
          </button>
          {can("members.write") && (
            <Link className="button primary" to="/members">
              + Add a member
            </Link>
          )}
        </div>
      </div>
      <div className="filter-bar">
        <label>
          Branch
          <select value={branch} onChange={(e) => setBranch(e.target.value)}>
            <option value="">All assigned branches</option>
            {branches?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          From
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </label>
        <label>
          To (exclusive)
          <input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </label>
        <span className="range-label">
          <CalendarDays size={16} />
          {data ? `${data.from_date} → ${data.to_date}` : "This month"}
        </span>
      </div>
      {error != null && <ErrorBox error={error} />}{" "}
      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <ErrorBox error={query.error} retry={() => query.refetch()} />
      ) : (
        data && (
          <>
            <div className="stats-grid">
              {[
                {
                  label: "Total members",
                  value: data.total_members,
                  sub: `${data.new_members} joined in this period`,
                  Icon: Users,
                  color: "blue",
                },
                {
                  label: "Active memberships",
                  value: data.active_members,
                  sub: `${data.expired_members} members with expired access`,
                  Icon: UserCheck,
                  color: "green",
                },
                {
                  label: "Cash collected",
                  value: currency(data.cash_collected, data.currency),
                  sub: "Recorded payments in selected period",
                  Icon: IndianRupee,
                  color: "purple",
                },
                {
                  label: "Today’s check-ins",
                  value: data.today_attendance,
                  sub: `Gym-local time · ${data.timezone}`,
                  Icon: ScanLine,
                  color: "orange",
                },
              ].map((c) => (
                <article className="stat-card" key={c.label}>
                  <div>
                    <span>{c.label}</span>
                    <span className={"stat-icon " + c.color}>
                      <c.Icon size={20} />
                    </span>
                  </div>
                  <strong>{c.value}</strong>
                  <small>{c.sub}</small>
                </article>
              ))}
            </div>
            <div className="dashboard-grid">
              <section className="card trend-card">
                <div className="card-head">
                  <div>
                    <h2>Club activity</h2>
                    <p>Daily check-ins · selected period</p>
                  </div>
                  <span className="legend">
                    <i /> Check-ins
                  </span>
                </div>
                <div
                  className="chart"
                  role="img"
                  aria-label="Daily attendance bar chart"
                >
                  {data.trend.map((d) => (
                    <div
                      className="bar-slot"
                      key={d.date}
                      title={`${d.date}: ${d.checkins} check-ins`}
                    >
                      <span
                        style={{
                          height:
                            Math.max(
                              d.checkins ? 4 : 1,
                              (d.checkins /
                                Math.max(
                                  1,
                                  ...data.trend.map((t) => t.checkins),
                                )) *
                                140,
                            ) + "px",
                        }}
                      />
                      <small>
                        {data.trend.length < 40 ? d.date.slice(8) : ""}
                      </small>
                    </div>
                  ))}
                </div>
                <div className="chart-foot">
                  <span>{data.trend[0]?.date}</span>
                  <span>{data.trend.at(-1)?.date}</span>
                </div>
              </section>
              <section className="card balance-card">
                <div className="card-head">
                  <div>
                    <div className="eyebrow">COLLECTIONS SNAPSHOT</div>
                    <h2>Keep a clear balance.</h2>
                  </div>
                  <ArrowUpRight size={20} />
                </div>
                <p>Outstanding dues</p>
                <strong>{currency(data.outstanding, data.currency)}</strong>
                <div className="balance-line">
                  <span>Net cash collected</span>
                  <b>{currency(data.net_cash_collected, data.currency)}</b>
                </div>
                <div className="balance-line">
                  <span>Refunds</span>
                  <b>{currency(data.refunds, data.currency)}</b>
                </div>
                <div className="balance-line">
                  <span>Expenses</span>
                  <b>{currency(data.expenses, data.currency)}</b>
                </div>
                <Link to="/billing">
                  View billing <ArrowUpRight size={16} />
                </Link>
              </section>
              <section className="card">
                <div className="card-head">
                  <div>
                    <h2>Renewals on the horizon</h2>
                    <p>Memberships ending within seven days</p>
                  </div>
                  <span className="count">{data.expiring.length}</span>
                </div>
                {data.expiring.length ? (
                  <div className="renewal-list">
                    {data.expiring.slice(0, 8).map((m) => (
                      <div key={m.member_id + m.end_date}>
                        <span className="avatar pale">
                          {m.member_name.slice(0, 1)}
                        </span>
                        <div>
                          <strong>{m.member_name}</strong>
                          <small>Access ends {m.end_date}</small>
                        </div>
                        <span className="badge warn">{m.days_left} days</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Empty text="No upcoming expiries. You’re all caught up." />
                )}
              </section>
              <section className="card">
                <div className="card-head">
                  <div>
                    <h2>Operational pulse</h2>
                    <p>What needs your attention</p>
                  </div>
                  <Clock3 size={18} />
                </div>
                <div className="pulse-row">
                  <Package size={18} />
                  <span>Low-stock items</span>
                  <b>{data.low_stock}</b>
                </div>
                <div className="pulse-row">
                  <Clock3 size={18} />
                  <span>Equipment service due</span>
                  <b>{data.maintenance_due}</b>
                </div>
                <div className="pulse-row">
                  <UserCheck size={18} />
                  <span>Cohort retention</span>
                  <b>
                    {data.retention_pct == null
                      ? "—"
                      : data.retention_pct + "%"}
                  </b>
                </div>
                <small className="muted-text">
                  Retention compares members active at the period start with
                  members active today. Cohort: {data.retention_cohort}.
                </small>
              </section>
            </div>
            {reports && (
              <div className="quick-grid">
                <section className="card">
                  <h2>Branch comparison</h2>
                  {data.branches.map((b) => (
                    <div className="pulse-row" key={b.branch_id}>
                      <span>
                        {b.name}
                        <small>{b.members} members</small>
                      </span>
                      <b>{currency(b.collected, data.currency)}</b>
                    </div>
                  ))}
                </section>
                <section className="card">
                  <h2>Trainer workload</h2>
                  {data.trainer_workload.length ? (
                    data.trainer_workload.map((t, i) => (
                      <div className="pulse-row" key={i}>
                        <span>{t.name}</span>
                        <b>
                          {t.completed} / {t.sessions} completed
                        </b>
                      </div>
                    ))
                  ) : (
                    <Empty />
                  )}
                </section>
              </div>
            )}
            <p className="footnote">
              Cash collections and invoice totals are operational metrics.
              Accrual-based revenue recognition is not calculated.
            </p>
          </>
        )
      )}
    </>
  );
}
