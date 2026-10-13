import { useState } from "react";
import { Navigate, Link, useSearchParams } from "react-router-dom";
import {
  Dumbbell,
  ArrowRight,
  ShieldCheck,
  Users,
  Activity,
} from "lucide-react";
import { useAuth } from "../auth";
import { api, send } from "../api";
import { Form, type Field } from "../components/ui";
export default function Login() {
  const { info, login } = useAuth();
  const [mode, setMode] = useState<"login" | "register" | "forgot">("login"),
    [notice, setNotice] = useState("");
  if (info) return <Navigate to="/" replace />;
  const fields: Field[] =
    mode === "register"
      ? [
          {
            name: "organization",
            label: "Gym / organization name",
            required: true,
          },
          {
            name: "slug",
            label: "Organization ID",
            required: true,
            hint: "Lowercase letters, numbers and hyphens; 3–60 characters.",
          },
          { name: "name", label: "Your name", required: true },
          { name: "email", label: "Email", type: "email", required: true },
          {
            name: "password",
            label: "Password",
            type: "password",
            required: true,
            hint: "At least 12 characters.",
          },
        ]
      : [
          { name: "organization", label: "Organization ID", required: true },
          { name: "email", label: "Email", type: "email", required: true },
          ...(mode === "login"
            ? [
                {
                  name: "password",
                  label: "Password",
                  type: "password",
                  required: true,
                },
              ]
            : []),
        ];
  return (
    <div className="auth-layout">
      <section className="auth-story">
        <Link to="/" className="brand">
          <span className="brand-icon">
            <Dumbbell />
          </span>
          <span>
            GymOS<small>ENTERPRISE</small>
          </span>
        </Link>
        <div>
          <div className="eyebrow">CONNECTED CLUB OPERATIONS</div>
          <h1>
            More time for
            <br />
            <em>stronger members.</em>
          </h1>
          <p>
            Your members, memberships and everyday operations. One clear view of
            your gym.
          </p>
          <div className="story-points">
            <span>
              <Users />
              Member relationships
            </span>
            <span>
              <Activity />
              Training & attendance
            </span>
            <span>
              <ShieldCheck />
              Controlled team access
            </span>
          </div>
        </div>
        <small>GymOS Enterprise · Built for your daily rhythm</small>
      </section>
      <section className="auth-form">
        <div className="auth-card">
          <div className="eyebrow">LET’S GET MOVING</div>
          <h2>
            {mode === "login"
              ? "Welcome back"
              : mode === "register"
                ? "Create your workspace"
                : "Reset your password"}
          </h2>
          <p>
            {mode === "login"
              ? "Sign in to keep your club running smoothly."
              : mode === "register"
                ? "Set up your organization, then add a branch."
                : "Enter your organization ID and account email."}
          </p>
          {notice && (
            <div role="status" className="notice">
              {notice}
            </div>
          )}
          <Form
            key={mode}
            fields={fields}
            label={
              mode === "login"
                ? "Sign in →"
                : mode === "register"
                  ? "Create workspace →"
                  : "Send reset instructions"
            }
            submit={async (d) => {
              if (mode === "forgot") {
                const r = await api<{ message: string }>(
                  "/auth/forgot-password",
                  send(d),
                );
                setNotice(r.message);
              } else await login(d, mode === "register");
            }}
          />
          <div className="auth-links">
            {mode === "login" ? (
              <>
                <button
                  onClick={() => {
                    setMode("forgot");
                    setNotice("");
                  }}
                >
                  Forgot password?
                </button>
                <button
                  onClick={() => {
                    setMode("register");
                    setNotice("");
                  }}
                >
                  Create a workspace <ArrowRight size={14} />
                </button>
              </>
            ) : (
              <button
                onClick={() => {
                  setMode("login");
                  setNotice("");
                }}
              >
                Back to sign in
              </button>
            )}
          </div>
          <small>
            For the local demo, use the credentials created by the setup script.
            No account is created automatically.
          </small>
        </div>
      </section>
    </div>
  );
}
export function Activate() {
  const [params] = useSearchParams();
  const [done, setDone] = useState(false);
  return (
    <div className="activation">
      <h1>Set your GymOS password</h1>
      {done ? (
        <>
          <p>Password saved. You can now sign in.</p>
          <Link to="/login">Continue to sign in</Link>
        </>
      ) : (
        <Form
          fields={[
            {
              name: "password",
              label: "New password",
              type: "password",
              required: true,
              hint: "At least 12 characters.",
            },
          ]}
          submit={(d) =>
            api(
              "/auth/reset-password",
              send({ ...d, token: params.get("token") }),
            )
          }
          onDone={() => setDone(true)}
        />
      )}
    </div>
  );
}
