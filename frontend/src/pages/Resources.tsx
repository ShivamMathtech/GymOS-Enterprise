import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, send, localDay } from "../api";
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
  type Field,
  type Column,
} from "../components/ui";
import type { Page, Row } from "../types";
type Config = {
  slug: string;
  label: string;
  fields: Field[];
  columns: string[];
  editable?: boolean;
};
export function ResourceModule({
  group,
}: {
  group: "training" | "workouts" | "inventory" | "expenses";
}) {
  const { can, info } = useAuth();
  const qc = useQueryClient();
  const [active, setActive] = useState(0),
    [page, setPage] = useState(1),
    [search, setSearch] = useState(""),
    [modal, setModal] = useState(""),
    [row, setRow] = useState<Row | null>(null),
    [action, setAction] = useState("");
  const training = group === "training" || group === "workouts";
  const branches = useRows("/branches"),
    members = useRows("/members", training),
    trainers = useRows("/trainers", training),
    trainerAccounts = useRows("/trainer-accounts", group === "training"),
    packages = useRows("/training-packages", training),
    exercises = useRows("/exercises", group === "workouts"),
    workouts = useRows("/workouts", group === "workouts"),
    suppliers = useRows("/suppliers", group === "inventory"),
    inventory = useRows("/inventory", group === "inventory"),
    equipment = useRows("/equipment", group === "inventory");
  const f = (
    name: string,
    label: string,
    type = "text",
    required = true,
    extra: Partial<Field> = {},
  ): Field => ({ name, label, type, required, ...extra });
  const branch = f("branch_id", "Branch", "text", true, {
      options: options(branches.data),
    }),
    member = f("member_id", "Member", "text", true, {
      options: options(members.data),
    }),
    trainer = f("trainer_id", "Trainer", "text", true, {
      options: options(trainers.data),
    }),
    exercise = f("exercise_id", "Exercise", "text", true, {
      options: options(exercises.data),
    });
  let configs: Config[] =
    group === "training"
      ? [
          {
            slug: "trainers",
            label: "Trainer directory",
            fields: [
              branch,
              f("name", "Trainer name"),
              f("user_id", "Trainer account", "text", false, {
                options: options(trainerAccounts.data),
                hint: "Optional. Invite and activate the trainer account first.",
              }),
              f("specialties", "Specialties", "text", false),
              f("starts", "Available from", "time", true, {
                defaultValue: "06:00",
              }),
              f("ends", "Available until", "time", true, {
                defaultValue: "21:00",
              }),
              f("working_days", "Working days", "multiselect", true, {
                defaultValue: ["0", "1", "2", "3", "4", "5"],
                options: [
                  "Monday",
                  "Tuesday",
                  "Wednesday",
                  "Thursday",
                  "Friday",
                  "Saturday",
                  "Sunday",
                ].map((label, i) => ({ value: String(i), label })),
                hint: "Hold Ctrl or Cmd to select multiple days.",
              }),
              f("active", "Active", "checkbox", false, { defaultValue: true }),
            ],
            columns: [
              "name",
              "specialties",
              "branch_id",
              "starts",
              "ends",
              "active",
            ],
            editable: true,
          },
          {
            slug: "trainer-assignments",
            label: "Client assignments",
            fields: [trainer, member],
            columns: ["trainer_id", "member_id"],
          },
          {
            slug: "training-packages",
            label: "Session packages",
            fields: [
              trainer,
              member,
              f("name", "Package name"),
              f("sessions", "Number of sessions", "number", true, { min: 1 }),
            ],
            columns: [
              "name",
              "trainer_id",
              "member_id",
              "sessions",
              "remaining",
            ],
          },
          {
            slug: "training-sessions",
            label: "Session schedule",
            fields: [
              trainer,
              member,
              f("package_id", "Package", "text", true, {
                options: options(packages.data),
              }),
              f("starts_at", "Starts (local time)", "datetime-local"),
              f("ends_at", "Ends (local time)", "datetime-local"),
            ],
            columns: [
              "trainer_id",
              "member_id",
              "starts_at",
              "ends_at",
              "state",
            ],
            editable: true,
          },
        ]
      : group === "workouts"
        ? [
            {
              slug: "exercises",
              label: "Exercise library",
              fields: [
                f("name", "Exercise name"),
                f("muscle_group", "Muscle group"),
                f("instructions", "Instructions", "textarea", false),
              ],
              columns: ["name", "muscle_group", "instructions"],
              editable: true,
            },
            {
              slug: "workouts",
              label: "Workout plans",
              fields: [
                f("name", "Plan name"),
                {
                  ...member,
                  required: false,
                  hint: "Leave empty to create a template.",
                },
                { ...trainer, required: info?.user.role === "Trainer" },
                f("description", "Description", "textarea", false),
                f("scheduled_date", "Scheduled date", "date", false),
              ],
              columns: ["name", "member_id", "trainer_id", "scheduled_date"],
              editable: true,
            },
            {
              slug: "workout-exercises",
              label: "Plan exercises",
              fields: [
                f("workout_plan_id", "Workout plan", "text", true, {
                  options: options(workouts.data),
                }),
                exercise,
                f("sets", "Sets", "number", true, { min: 1 }),
                f("repetitions", "Repetitions", "number", true, { min: 1 }),
                f("weight_kg", "Weight (kg)", "money", true, {
                  defaultValue: 0,
                }),
                f("duration_seconds", "Duration (seconds)", "number", true, {
                  defaultValue: 0,
                  min: 0,
                }),
              ],
              columns: [
                "workout_plan_id",
                "exercise_id",
                "sets",
                "repetitions",
                "weight_kg",
                "duration_seconds",
              ],
              editable: true,
            },
            {
              slug: "workout-logs",
              label: "Workout logs",
              fields: [
                member,
                exercise,
                f("performed_on", "Performed on", "date", true, {
                  defaultValue: localDay(),
                }),
                f("sets", "Sets", "number", true, { min: 1 }),
                f("repetitions", "Repetitions", "number", true, { min: 1 }),
                f("weight_kg", "Weight (kg)", "money", true, {
                  defaultValue: 0,
                }),
                f("duration_seconds", "Duration (seconds)", "number", true, {
                  defaultValue: 0,
                }),
              ],
              columns: [
                "member_id",
                "exercise_id",
                "performed_on",
                "sets",
                "repetitions",
                "weight_kg",
              ],
            },
            {
              slug: "progress",
              label: "Member progress",
              fields: [
                member,
                f("measured_on", "Measured on", "date", true, {
                  defaultValue: localDay(),
                }),
                f("weight_kg", "Body weight (kg)", "money"),
                f("waist_cm", "Waist (cm)", "money", false),
                f("notes", "Private trainer notes", "textarea", false),
              ],
              columns: ["member_id", "measured_on", "weight_kg", "waist_cm"],
            },
          ]
        : group === "inventory"
          ? [
              {
                slug: "inventory",
                label: "Stock catalog",
                fields: [
                  branch,
                  f("name", "Item name"),
                  f("sku", "SKU"),
                  f("supplier_id", "Supplier", "text", false, {
                    options: options(suppliers.data),
                  }),
                  f("low_stock_level", "Low-stock threshold", "number", true, {
                    defaultValue: 5,
                    min: 0,
                  }),
                ],
                columns: [
                  "name",
                  "sku",
                  "branch_id",
                  "stock",
                  "low_stock_level",
                ],
                editable: true,
              },
              {
                slug: "equipment",
                label: "Equipment",
                fields: [
                  branch,
                  f("name", "Equipment name"),
                  f("serial", "Serial / asset number"),
                  f("assigned_to", "Assigned area or person", "text", false),
                  f("next_service", "Next service", "date"),
                  f("state", "State", "text", true, {
                    defaultValue: "operational",
                    options: ["operational", "maintenance", "retired"].map(
                      (v) => ({ value: v, label: v }),
                    ),
                  }),
                ],
                columns: [
                  "name",
                  "serial",
                  "branch_id",
                  "assigned_to",
                  "next_service",
                  "state",
                ],
                editable: true,
              },
              {
                slug: "suppliers",
                label: "Suppliers",
                fields: [
                  f("name", "Supplier name"),
                  f("contact", "Contact details", "text", false),
                ],
                columns: ["name", "contact"],
                editable: true,
              },
            ]
          : [
              {
                slug: "expenses",
                label: "Expenses",
                fields: [
                  branch,
                  f("category", "Category"),
                  f("description", "Description"),
                  f("amount", "Amount", "money"),
                  f("expense_date", "Expense date", "date", true, {
                    defaultValue: localDay(),
                  }),
                ],
                columns: [
                  "category",
                  "description",
                  "amount",
                  "expense_date",
                  "branch_id",
                ],
              },
            ];
  if (info?.user.role === "Receptionist")
    configs = configs.filter(
      (c) => !["progress", "workout-logs"].includes(c.slug),
    );
  const config = configs[Math.min(active, configs.length - 1)],
    permission =
      (group === "expenses" ? "finance" : training ? "training" : "inventory") +
      ".write";
  const query = useQuery({
    queryKey: [config.slug, page, search],
    queryFn: () =>
      api<Page>(
        "/" +
          config.slug +
          "?page=" +
          page +
          "&q=" +
          encodeURIComponent(search),
      ),
  });
  const sources: Record<string, Row[] | undefined> = {
    branch_id: branches.data,
    member_id: members.data,
    trainer_id: trainers.data,
    exercise_id: exercises.data,
    workout_plan_id: workouts.data,
    supplier_id: suppliers.data,
  };
  const columns: Column[] = config.columns.map((k) => ({
    key: k,
    label: k.replaceAll("_", " ").replace(" id", ""),
    render: (r) =>
      sources[k] ? (
        rowName(sources[k], r[k])
      ) : ["state", "status", "active"].includes(k) ? (
        <Badge value={r[k]} />
      ) : k.endsWith("_at") ? (
        new Date(String(r[k])).toLocaleString()
      ) : (
        String(r[k] ?? "—")
      ),
  }));
  const close = () => {
    setModal("");
    setRow(null);
  };
  const refresh = () => {
    qc.invalidateQueries();
    close();
  };
  function normalize(d: Record<string, unknown>) {
    const copy = { ...d };
    for (const k of [
      "user_id",
      "member_id",
      "trainer_id",
      "supplier_id",
      "scheduled_date",
      "waist_cm",
    ])
      if (copy[k] === "") copy[k] = null;
    if (config.slug === "trainers")
      copy.working_days = (d.working_days as string[]).map(Number);
    if (config.slug === "training-sessions") {
      copy.starts_at = new Date(String(d.starts_at)).toISOString();
      copy.ends_at = new Date(String(d.ends_at)).toISOString();
    }
    return copy;
  }
  const editInitial = row
    ? {
        ...row,
        working_days: Array.isArray(row.working_days)
          ? row.working_days.map(String)
          : row.working_days,
        starts_at: row.starts_at
          ? localDateTime(String(row.starts_at))
          : undefined,
        ends_at: row.ends_at ? localDateTime(String(row.ends_at)) : undefined,
      }
    : {};
  const writeAllowed =
    can(permission) &&
    !(
      info?.user.role === "Trainer" &&
      ["trainers", "trainer-assignments", "training-packages"].includes(
        config.slug,
      )
    );
  return (
    <>
      {group !== "expenses" && (
        <div className="page-head">
          <div>
            <div className="eyebrow">
              {training ? "COACHING & PROGRESS" : "CLUB OPERATIONS"}
            </div>
            <h1>
              {group === "training"
                ? "Better coaching, on schedule."
                : group === "workouts"
                  ? "Turn effort into progress."
                  : "Keep your club in good shape."}
            </h1>
            <p>
              {training
                ? "Connect trainers, sessions and member goals."
                : "Manage stock, suppliers and equipment service."}
            </p>
          </div>
        </div>
      )}
      <div className="tabs">
        {configs.map((c, i) => (
          <button
            className={config.slug === c.slug ? "active" : ""}
            key={c.slug}
            onClick={() => {
              setActive(i);
              setPage(1);
              setSearch("");
            }}
          >
            {c.label}
          </button>
        ))}
      </div>
      <section className="card">
        <div className="toolbar">
          <input
            aria-label={"Search " + config.label}
            placeholder={"Search " + config.label.toLowerCase() + "…"}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
          {writeAllowed && (
            <button
              className="primary"
              onClick={() => {
                setRow(null);
                setModal("edit");
              }}
            >
              + Add record
            </button>
          )}
        </div>
        {query.isLoading ? (
          <Loading />
        ) : query.error ? (
          <ErrorBox error={query.error} retry={() => query.refetch()} />
        ) : (
          query.data && (
            <Table
              data={query.data}
              columns={columns}
              page={page}
              onPage={setPage}
              actions={(r) => (
                <>
                  {config.editable && writeAllowed && (
                    <button
                      onClick={() => {
                        setRow(r);
                        setModal("edit");
                      }}
                    >
                      Edit
                    </button>
                  )}
                  {config.slug === "training-sessions" &&
                    r.state === "booked" &&
                    writeAllowed &&
                    ["completed", "cancelled", "no_show"].map((v) => (
                      <button
                        key={v}
                        onClick={() => {
                          setRow(r);
                          setAction(v);
                          setModal("session-state");
                        }}
                      >
                        {v.replaceAll("_", " ")}
                      </button>
                    ))}
                  {config.slug === "inventory" && (
                    <>
                      <button
                        onClick={() => {
                          setRow(r);
                          setModal("stock-history");
                        }}
                      >
                        History
                      </button>
                      {writeAllowed && (
                        <button
                          onClick={() => {
                            setRow(r);
                            setModal("stock");
                          }}
                        >
                          Adjust stock
                        </button>
                      )}
                    </>
                  )}
                  {config.slug === "equipment" && (
                    <>
                      <button
                        onClick={() => {
                          setRow(r);
                          setModal("service-history");
                        }}
                      >
                        History
                      </button>
                      {writeAllowed && (
                        <button
                          onClick={() => {
                            setRow(r);
                            setModal("service");
                          }}
                        >
                          Record service
                        </button>
                      )}
                    </>
                  )}
                </>
              )}
            />
          )
        )}
      </section>
      {modal === "edit" && (
        <Modal
          title={(row ? "Edit " : "Add ") + config.label.toLowerCase()}
          onClose={close}
        >
          <Form
            fields={config.fields}
            initial={editInitial}
            submit={(d) =>
              api("/" + config.slug + (row ? "/" + row.id : ""), {
                method: row ? "PUT" : "POST",
                body: JSON.stringify(normalize(d)),
              })
            }
            onDone={refresh}
          />
        </Modal>
      )}
      {modal === "session-state" && row && (
        <Confirm
          title="Update session attendance"
          message={
            "Mark this session as " +
            action.replaceAll("_", " ") +
            "? Closed sessions cannot be changed."
          }
          onClose={close}
          onConfirm={async () => {
            await api(
              "/training-sessions/" + row.id + "/state",
              send({ state: action }),
            );
            refresh();
          }}
        />
      )}
      {modal === "stock" && row && (
        <Modal title="Record stock movement" onClose={close}>
          <p className="modal-copy">
            Current stock: {String(row.stock)}. Use positive quantities for
            receipts and negative quantities for issues or corrections.
          </p>
          <Form
            fields={[
              f("quantity", "Quantity change", "number"),
              f("reason", "Movement reason", "textarea"),
            ]}
            submit={(d) =>
              api("/stock-movements", send({ ...d, item_id: row.id }))
            }
            onDone={refresh}
          />
        </Modal>
      )}
      {modal === "service" && row && (
        <Modal title="Record equipment service" onClose={close}>
          <Form
            fields={[
              f("serviced_on", "Service date", "date", true, {
                defaultValue: localDay(),
              }),
              f("next_service", "Next service date", "date"),
              f("cost", "Service cost", "money", true, { defaultValue: 0 }),
              f("notes", "Service notes", "textarea"),
            ]}
            submit={(d) =>
              api("/maintenance", send({ ...d, equipment_id: row.id }))
            }
            onDone={refresh}
          />
        </Modal>
      )}
      {modal.endsWith("history") && row && (
        <ResourceHistory
          path={
            modal === "stock-history"
              ? "/stock-movements?item_id=" + row.id
              : "/maintenance?equipment_id=" + row.id
          }
          stock={modal === "stock-history"}
          onClose={close}
        />
      )}
    </>
  );
}
function localDateTime(s: string) {
  const d = new Date(s);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
function ResourceHistory({
  path,
  stock,
  onClose,
}: {
  path: string;
  stock: boolean;
  onClose: () => void;
}) {
  const [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: ["resource-history", path, page],
    queryFn: () => api<Page>(path + "&page=" + page),
  });
  return (
    <Modal
      title={stock ? "Stock movement history" : "Maintenance history"}
      onClose={onClose}
    >
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
            columns={(stock
              ? ["created_at", "quantity", "reason"]
              : ["serviced_on", "cost", "notes"]
            ).map((k) => ({ key: k, label: k.replaceAll("_", " ") }))}
          />
        )
      )}
    </Modal>
  );
}
