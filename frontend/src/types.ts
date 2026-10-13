export type Row = { id: string; [key: string]: unknown };
export type Page<T = Row> = {
  items: T[];
  total: number;
  page: number;
  size: number;
};
export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  active: boolean;
};
export type Organization = {
  id: string;
  name: string;
  slug: string;
  currency: string;
  timezone: string;
  invoice_prefix: string;
};
export type AuthInfo = {
  user: User;
  permissions: string[];
  branch_ids: string[] | null;
  organization: Organization;
};
export type Branch = Row & { name: string; timezone: string };
export type Member = Row & {
  name: string;
  member_code: string;
  phone: string;
  status: string;
  branch_id: string;
};
export type Invoice = Row & {
  number: string;
  member_id: string;
  total: string;
  balance: string;
  status: string;
  currency: string;
};
export type Dashboard = {
  from_date: string;
  to_date: string;
  timezone: string;
  currency: string;
  total_members: number;
  active_members: number;
  expired_members: number;
  new_members: number;
  today_attendance: number;
  cash_collected: string;
  refunds: string;
  net_cash_collected: string;
  outstanding: string;
  invoiced_total: string;
  expenses: string;
  retention_pct: number | null;
  churn_pct: number | null;
  retention_cohort: number;
  low_stock: number;
  maintenance_due: number;
  trend: {
    date: string;
    collected: string;
    refunds: string;
    checkins: number;
  }[];
  branches: {
    branch_id: string;
    name: string;
    members: number;
    collected: string;
  }[];
  expiring: {
    member_id: string;
    member_name: string;
    end_date: string;
    days_left: number;
  }[];
  trainer_workload: { name: string; sessions: number; completed: number }[];
};
