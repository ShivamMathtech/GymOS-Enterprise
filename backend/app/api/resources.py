"""Typed resource endpoints for catalog and recording modules, with shared tenant policy."""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from app import models as m, schemas as s
from app.db import get_db
from app.deps import Actor, require, owned, get_member, member_scope, own_trainer
from app.services.common import audit, public, page

router = APIRouter(tags=["Training, inventory & expenses"])
RESOURCES = {
    "trainers": (
        m.Trainer,
        s.TrainerIn,
        "training",
        "id created_at branch_id user_id name specialties starts ends working_days active",
        True,
    ),
    "trainer-assignments": (
        m.TrainerAssignment,
        s.AssignmentIn,
        "training",
        "id created_at trainer_id member_id",
        False,
    ),
    "training-packages": (
        m.TrainingPackage,
        s.PackageIn,
        "training",
        "id created_at trainer_id member_id name sessions",
        False,
    ),
    "exercises": (m.Exercise, s.ExerciseIn, "training", "id created_at name muscle_group instructions", True),
    "workouts": (
        m.WorkoutPlan,
        s.WorkoutIn,
        "training",
        "id created_at name member_id trainer_id description scheduled_date",
        True,
    ),
    "workout-exercises": (
        m.WorkoutExercise,
        s.WorkoutExerciseIn,
        "training",
        "id created_at workout_plan_id exercise_id sets repetitions weight_kg duration_seconds",
        True,
    ),
    "workout-logs": (
        m.WorkoutLog,
        s.WorkoutLogIn,
        "training",
        "id created_at member_id exercise_id performed_on sets repetitions weight_kg duration_seconds",
        False,
    ),
    "progress": (
        m.Progress,
        s.ProgressIn,
        "training",
        "id created_at member_id measured_on weight_kg waist_cm notes",
        False,
    ),
    "expenses": (
        m.Expense,
        s.ExpenseIn,
        "finance",
        "id created_at branch_id category description amount expense_date",
        False,
    ),
    "suppliers": (m.Supplier, s.SupplierIn, "inventory", "id created_at name contact", True),
    "inventory": (
        m.InventoryItem,
        s.InventoryIn,
        "inventory",
        "id created_at branch_id supplier_id name sku stock low_stock_level",
        True,
    ),
    "equipment": (
        m.Equipment,
        s.EquipmentIn,
        "inventory",
        "id created_at branch_id name serial assigned_to next_service state",
        True,
    ),
}


def filter_resource(db, a, model, q):
    q = q.where(model.org_id == a.org_id)
    if model in {m.Progress, m.WorkoutLog} and a.user.role == "Receptionist":
        raise HTTPException(403, "Private training records require trainer or manager access")
    if model == m.WorkoutExercise:
        q = q.where(
            m.WorkoutExercise.workout_plan_id.in_(filter_resource(db, a, m.WorkoutPlan, select(m.WorkoutPlan.id)))
        )
    if hasattr(model, "branch_id") and a.branches is not None:
        q = q.where(model.branch_id.in_(a.branches))
    if hasattr(model, "member_id"):
        ids = member_scope(db, a, select(m.Member.id))
        q = q.where(or_(model.member_id.in_(ids), model.member_id.is_(None)))
    if a.user.role == "Trainer":
        trainer = own_trainer(db, a)
        if model == m.Trainer:
            q = q.where(m.Trainer.user_id == a.user.id)
        elif hasattr(model, "trainer_id"):
            q = q.where(model.trainer_id == (trainer.id if trainer else ""))
        elif model == m.WorkoutExercise:
            q = q.where(
                m.WorkoutExercise.workout_plan_id.in_(
                    select(m.WorkoutPlan.id).where(
                        m.WorkoutPlan.org_id == a.org_id, m.WorkoutPlan.trainer_id == (trainer.id if trainer else "")
                    )
                )
            )
    return q


def validate_resource(db, a, slug, values, existing=None):
    if values.get("branch_id"):
        owned(db, m.Branch, values["branch_id"], a)
    if values.get("member_id"):
        get_member(db, values["member_id"], a)
    trainer = None
    if values.get("trainer_id"):
        trainer = owned(db, m.Trainer, values["trainer_id"], a)
    if a.user.role == "Trainer":
        own = own_trainer(db, a)
        if slug in {"trainers", "trainer-assignments", "training-packages"}:
            raise HTTPException(403, "Managers manage trainer profiles and packages")
        if slug == "workouts" and (not own or values.get("trainer_id") != own.id):
            raise HTTPException(403, "Assign your own trainer profile")
        if trainer and trainer.user_id != a.user.id:
            raise HTTPException(403, "Trainer assignment denied")
    if slug == "trainers" and values.get("user_id"):
        user = owned(db, m.User, values["user_id"], a)
        if user.role != "Trainer":
            raise HTTPException(422, "Linked account must have the Trainer role")
        if not db.scalar(
            select(m.StaffAssignment).where(
                m.StaffAssignment.org_id == a.org_id,
                m.StaffAssignment.user_id == user.id,
                m.StaffAssignment.branch_id == values["branch_id"],
            )
        ):
            raise HTTPException(422, "Trainer account needs this branch assignment")
    if slug == "trainers" and values["starts"] >= values["ends"]:
        raise HTTPException(422, "Trainer availability must end after it starts (same local day)")
    if slug in {"trainer-assignments", "training-packages"}:
        member = get_member(db, values["member_id"], a)
        if member.branch_id != trainer.branch_id:
            raise HTTPException(422, "Member and trainer must share a branch")
        if slug == "training-packages" and not db.scalar(
            select(m.TrainerAssignment).where(
                m.TrainerAssignment.org_id == a.org_id,
                m.TrainerAssignment.member_id == member.id,
                m.TrainerAssignment.trainer_id == trainer.id,
            )
        ):
            raise HTTPException(422, "Assign the client to this trainer first")
    if slug == "workouts" and values.get("member_id") and trainer:
        if not db.scalar(
            select(m.TrainerAssignment).where(
                m.TrainerAssignment.org_id == a.org_id,
                m.TrainerAssignment.member_id == values["member_id"],
                m.TrainerAssignment.trainer_id == trainer.id,
            )
        ):
            raise HTTPException(422, "Assign this client to the trainer first")
    if values.get("exercise_id"):
        owned(db, m.Exercise, values["exercise_id"], a)
    if values.get("workout_plan_id"):
        plan = db.scalar(
            filter_resource(
                db, a, m.WorkoutPlan, select(m.WorkoutPlan).where(m.WorkoutPlan.id == values["workout_plan_id"])
            )
        )
        if not plan:
            raise HTTPException(404, "Workout not found")
    if values.get("supplier_id"):
        owned(db, m.Supplier, values["supplier_id"], a)
    if existing and "branch_id" in values and values["branch_id"] != existing.branch_id:
        raise HTTPException(409, "Moving historical records between branches is not supported; create a new record")


def register_resource(slug, model, schema, group, fields, editable):
    def listing(
        q: str = Query("", max_length=100),
        branch_id: str | None = None,
        member_id: str | None = None,
        trainer_id: str | None = None,
        workout_plan_id: str | None = None,
        page_no: int = Query(1, ge=1, alias="page"),
        size: int = Query(25, ge=1, le=100),
        a: Actor = Depends(require(group + ".read")),
        db: Session = Depends(get_db, scope="function"),
    ):
        stmt = filter_resource(db, a, model, select(model))
        if q and hasattr(model, "name"):
            stmt = stmt.where(model.name.ilike("%" + q.replace("%", "\\%").replace("_", "\\_") + "%"))
        for k, v in {
            "branch_id": branch_id,
            "member_id": member_id,
            "trainer_id": trainer_id,
            "workout_plan_id": workout_plan_id,
        }.items():
            if v and hasattr(model, k):
                stmt = stmt.where(getattr(model, k) == v)
        rows, total = page(db, stmt, model, page_no, size)
        items = [public(r, fields) for r in rows]
        if slug == "training-packages":
            from sqlalchemy import func

            for item in items:
                used = db.scalar(
                    select(func.count())
                    .select_from(m.TrainingSession)
                    .where(
                        m.TrainingSession.org_id == a.org_id,
                        m.TrainingSession.package_id == item["id"],
                        m.TrainingSession.state != "cancelled",
                    )
                )
                item["remaining"] = item["sessions"] - used
        return {"items": items, "total": total, "page": page_no, "size": size}

    def create(data, a: Actor = Depends(require(group + ".write")), db: Session = Depends(get_db, scope="function")):
        values = data.model_dump()
        validate_resource(db, a, slug, values)
        row = model(org_id=a.org_id, **values)
        db.add(row)
        db.flush()
        audit(db, a, slug + ".create", row.id)
        return public(row, fields)

    create.__annotations__["data"] = schema
    router.add_api_route("/" + slug, listing, methods=["GET"], name="list_" + slug)
    router.add_api_route("/" + slug, create, methods=["POST"], status_code=201, name="create_" + slug)
    if editable:

        def edit(
            key: str,
            data,
            a: Actor = Depends(require(group + ".write")),
            db: Session = Depends(get_db, scope="function"),
        ):
            row = db.scalar(filter_resource(db, a, model, select(model).where(model.id == key)).with_for_update())
            if not row:
                raise HTTPException(404, "Record not found")
            values = data.model_dump()
            validate_resource(db, a, slug, values, row)
            for k, v in values.items():
                setattr(row, k, v)
            audit(db, a, slug + ".update", row.id)
            return public(row, fields)

        edit.__annotations__["data"] = schema
        router.add_api_route("/" + slug + "/{key}", edit, methods=["PUT"], name="edit_" + slug)


for slug, args in RESOURCES.items():
    register_resource(slug, *args)
