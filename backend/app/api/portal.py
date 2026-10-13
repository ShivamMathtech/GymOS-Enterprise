from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models as m, schemas as s
from app.db import get_db
from app.deps import Actor, require
from app.services.common import public, audit
from app.services import billing, memberships
from app.api.crm import member_dto

router = APIRouter(prefix="/portal", tags=["Member portal"])


def profile(db, a):
    row = db.scalar(select(m.Member).where(m.Member.org_id == a.org_id, m.Member.user_id == a.user.id))
    if not row:
        raise HTTPException(404, "Your account is not linked to a member profile")
    return row


@router.get("")
def portal(a: Actor = Depends(require("self.read")), db: Session = Depends(get_db, scope="function")):
    member = profile(db, a)
    ms = db.scalars(
        select(m.Membership)
        .where(m.Membership.org_id == a.org_id, m.Membership.member_id == member.id)
        .order_by(m.Membership.created_at.desc())
        .limit(100)
    ).all()
    invoices = db.scalars(
        select(m.Invoice)
        .where(m.Invoice.org_id == a.org_id, m.Invoice.member_id == member.id)
        .order_by(m.Invoice.created_at.desc())
        .limit(100)
    ).all()
    attendance = db.scalars(
        select(m.Attendance)
        .where(m.Attendance.org_id == a.org_id, m.Attendance.member_id == member.id)
        .order_by(m.Attendance.checked_in_at.desc())
        .limit(100)
    ).all()
    sessions = db.scalars(
        select(m.TrainingSession)
        .where(m.TrainingSession.org_id == a.org_id, m.TrainingSession.member_id == member.id)
        .order_by(m.TrainingSession.starts_at.desc())
        .limit(100)
    ).all()
    workouts = db.scalars(
        select(m.WorkoutPlan)
        .where(m.WorkoutPlan.org_id == a.org_id, m.WorkoutPlan.member_id == member.id)
        .order_by(m.WorkoutPlan.created_at.desc())
        .limit(100)
    ).all()
    exercises = db.scalars(
        select(m.WorkoutExercise).where(
            m.WorkoutExercise.org_id == a.org_id, m.WorkoutExercise.workout_plan_id.in_([r.id for r in workouts])
        )
    ).all()
    progress = db.scalars(
        select(m.Progress)
        .where(m.Progress.org_id == a.org_id, m.Progress.member_id == member.id)
        .order_by(m.Progress.measured_on.desc())
        .limit(100)
    ).all()
    return {
        "member": member_dto(member, a),
        "memberships": [memberships.dto(db, a, r) for r in ms],
        "invoices": [billing.invoice_dto(db, r) for r in invoices],
        "attendance": [public(r, "id checked_in_at checked_out_at branch_id") for r in attendance],
        "sessions": [public(r, "id trainer_id starts_at ends_at state") for r in sessions],
        "workouts": [public(r, "id name description scheduled_date") for r in workouts],
        "workout_exercises": [
            public(r, "id workout_plan_id exercise_id sets repetitions weight_kg duration_seconds") for r in exercises
        ],
        "progress": [public(r, "id measured_on weight_kg waist_cm") for r in progress],
        "exercise_library": [
            public(r, "id name muscle_group instructions")
            for r in db.scalars(select(m.Exercise).where(m.Exercise.org_id == a.org_id))
        ],
    }


@router.post("/workout-logs", status_code=201)
def log(
    data: s.WorkoutLogIn, a: Actor = Depends(require("self.write")), db: Session = Depends(get_db, scope="function")
):
    member = profile(db, a)
    if data.member_id != member.id:
        raise HTTPException(403, "Only your own workout can be recorded")
    exercise = db.scalar(select(m.Exercise).where(m.Exercise.id == data.exercise_id, m.Exercise.org_id == a.org_id))
    if not exercise:
        raise HTTPException(404, "Exercise not found")
    row = m.WorkoutLog(org_id=a.org_id, **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, a, "workout.log", row.id)
    return public(row, "id member_id exercise_id performed_on sets repetitions weight_kg duration_seconds")
