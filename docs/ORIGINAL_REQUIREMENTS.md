# MASTER DEVELOPMENT PROMPT — GymOS Enterprise

## Project Objective

Build a complete, production-oriented, enterprise-level Gym Management and Fitness Club ERP called **GymOS Enterprise**.

The system must run locally on Windows and use:

- Frontend: React + Vite + TypeScript
- Styling: Tailwind CSS with reusable accessible UI components
- Backend: Python 3.12+ compatible FastAPI application
- Database: PostgreSQL
- ORM: SQLAlchemy 2.x
- Database migrations: Alembic
- Validation: Pydantic
- Authentication: secure access and refresh token strategy
- API: versioned REST API under `/api/v1`
- Testing: Pytest, HTTPX, Vitest and Playwright
- Local infrastructure: Docker Compose for PostgreSQL and optional supporting services

Do not build a static mockup, a frontend-only prototype, or an application filled with fake data. Implement real workflows backed by the database.

## 1. Engineering Requirements

Use a modular monolith with independent business modules, clear service boundaries, dependency injection, typed schemas, centralized configuration and consistent error handling.

Requirements:

- Use async database access consistently if using SQLAlchemy's async engine.
- Use Alembic for every database schema change.
- Never create production database tables through automatic startup `create_all`.
- Use environment variables for secrets and configuration.
- Never hardcode production credentials or API keys.
- Add structured logs, request IDs, health checks and meaningful validation errors.
- Provide pagination, filtering, sorting and search for large datasets.
- Add database indexes, foreign keys, uniqueness constraints and transactions where appropriate.
- Use UTC timestamps internally and support configurable gym-local time zones.
- Use Decimal or database numeric types for money; never use floating-point arithmetic for financial calculations.
- Use explicit DTOs and avoid returning ORM objects directly.
- Generate interactive API documentation through FastAPI OpenAPI.

## 2. Organization and Branch Management

Implement:

- Organization registration and settings
- Multiple branches under one organization
- Branch-specific working hours, time zones and membership policies
- Organization and branch staff assignments
- Branch-level reports and consolidated organization reports
- Tenant isolation on every organization-scoped API and database query
- Tests proving users cannot access another organization's records

Use a tenant-aware data model with explicit organization and branch relationships.

## 3. Authentication and Authorization

Implement:

- Login and logout
- User invitation and account activation
- Password hashing with Argon2 or another maintained secure password-hashing implementation
- Access tokens with short expiry
- Secure refresh-token rotation and revocation
- Forgot-password and reset-password flows
- Session/device management where practical
- Role-based and permission-based access control
- Rate limiting for sensitive authentication endpoints
- Audit events for security-sensitive actions

Roles: Super Admin, Gym Owner, Manager, Receptionist, Trainer, Accountant and Member.

Enforce authorization in backend services and API dependencies. The frontend must never be the only security boundary.

For browser authentication, choose an appropriate secure cookie strategy or a carefully implemented token strategy. Avoid storing long-lived sensitive tokens in localStorage. Protect cookie-based state-changing requests against CSRF.

## 4. Member CRM

Build complete member management:

- Create, view, update, deactivate and archive member profiles
- Member ID generation
- Profile photos with validated file uploads
- Contact information and emergency contacts
- Membership history and payment history
- Search by name, phone, member ID and membership status
- Filters, pagination and sorting
- Notes with restricted permissions
- Member import from CSV with validation and error reporting
- Export authorized member data to CSV
- Duplicate detection and appropriate database constraints

Keep personal information protected. Do not expose sensitive member information to unauthorized trainers or receptionists.

## 5. Membership Management

Implement:

- Configurable monthly, quarterly, half-yearly, annual and custom-duration plans
- Plan pricing, discounts, taxes and access rules
- Membership purchases and assignments
- Start date, end date and lifecycle status
- Renewals, upgrades, downgrades, freezes, extensions and cancellations
- Expiry alerts and configurable grace periods
- Membership status derived consistently from dates and lifecycle rules
- Payment-linked membership activation
- Complete membership audit history

Handle overlapping memberships, expired plans, duplicate renewals and concurrent requests safely.

## 6. Attendance

Implement:

- Member check-in and check-out
- QR-based member check-in with server-side token validation
- Receptionist-assisted manual check-in
- Duplicate check-in prevention
- Attendance history and daily/monthly summaries
- Branch and membership eligibility checks
- Authorized corrections with audit logs
- Attendance reports by member, trainer, branch and date
- Optional hardware integration interfaces for compatible access-control devices

Do not treat a client-generated member ID or unverified QR payload as proof of authorization.

## 7. Trainer and Workout Management

Implement:

- Trainer profiles and specialties
- Trainer availability and working schedules
- Client assignments
- Personal training packages and session balances
- Session booking, rescheduling, cancellation and attendance
- Workout plan templates
- Exercise library and workout scheduling
- Sets, repetitions, weights, duration and workout logs
- Member progress tracking with appropriate access controls

Prevent conflicting trainer bookings using appropriate database constraints or transactional locking.

## 8. Billing and Financial Management

Implement:

- Invoices and sequential invoice numbering scoped appropriately
- Invoice line items, discounts and configurable taxes
- Cash, UPI, card, bank transfer and other configurable payment methods
- Partial payments and outstanding balances
- Receipts and payment history
- Refunds and cancellation records
- Expense management and expense categories
- Daily collections and monthly financial summaries
- Revenue, dues and payment reconciliation reports
- CSV exports

Use immutable financial transaction records where appropriate. Corrections and refunds must be represented explicitly instead of silently deleting financial history.

Support manual payment recording for local development. Integrate a real payment gateway only when valid credentials, webhooks, signature verification and idempotent processing are configured. Never claim a payment succeeded based solely on a frontend redirect.

## 9. Inventory and Equipment

Implement:

- Equipment and inventory catalogs
- Stock receipts and stock adjustments
- Supplier records
- Equipment assignment and maintenance schedules
- Maintenance history and service expenses
- Low-stock alerts
- Inventory movement audit trails

## 10. Notifications and Background Jobs

Build an extensible notification service for:

- Membership expiry reminders
- Upcoming renewals
- Payment receipts
- Trainer session reminders
- Important administrative alerts

Support in-app notifications first. Add email/SMS integrations through configurable providers. Use a background job mechanism for scheduled notifications and retry transient failures safely. The application must still start when optional external providers are not configured.

## 11. Dashboard and Analytics

Build role-specific dashboards containing:

- Total, active, expired and new members
- Today's attendance and check-in activity
- Daily, weekly and monthly collections
- Outstanding payments
- Membership expiry trends
- Member retention and churn indicators
- Trainer workload and session completion
- Branch comparison
- Inventory and maintenance alerts

Define the calculation rules for every metric. Use actual database data, date filters, pagination where relevant and appropriately scoped queries. Clearly distinguish cash collected from recognized revenue where accounting rules require it.

## 12. Frontend and UI/UX

Create a polished professional enterprise dashboard.

Visual direction:

- Dark navy or charcoal sidebar
- Clean light or dark content surfaces with consistent contrast
- Blue primary accents and green success states
- Responsive layouts for desktop, tablet and mobile
- Rounded cards, restrained shadows and subtle animations
- Lucide icons, accessible forms and consistent spacing
- Data tables with search, sorting, filters and pagination
- Reusable modal, drawer, dropdown, toast and confirmation components
- Loading skeletons, empty states, error states and retry actions
- Accessible labels, keyboard navigation and visible focus states

Required screens:

1. Login and password recovery
2. Main dashboard
3. Members list, registration and member details
4. Membership plans and membership lifecycle
5. Attendance and QR check-in
6. Trainer directory and schedules
7. Workout plans and exercise tracking
8. Invoices, payments, refunds and expenses
9. Inventory and maintenance
10. Analytics and reports
11. User roles, permissions and staff management
12. Branches, organization settings and audit logs
13. Member self-service portal

Use React Router, a consistent API client, typed API contracts, centralized authentication handling and a query/cache library such as TanStack Query.

Every visible action must perform a real operation or be clearly identified as unavailable. Do not create decorative buttons, dead links or fabricated success messages.

## 13. Database Design

Create normalized models for:

- organizations
- branches
- users
- roles and permissions
- staff assignments
- members
- membership plans
- memberships and membership events
- attendance records
- trainers and trainer assignments
- exercises and workout plans
- training sessions
- invoices and invoice items
- payments and refunds
- expenses
- inventory items and stock movements
- equipment and maintenance records
- notifications
- audit logs
- refresh sessions or token records

Add primary keys, foreign keys, tenant ownership, timestamps, indexes and uniqueness constraints where appropriate.

Use transactions for operations that change multiple related records. Store monetary values using appropriate fixed-precision database types.

## 14. API Design

Use `/api/v1` with resource-oriented endpoints, appropriate HTTP methods, consistent status codes and structured error responses.

Include:

- Authentication and account management
- Members and member history
- Plans, memberships and renewals
- Attendance
- Trainers, schedules and workouts
- Invoices, payments, refunds and expenses
- Inventory and equipment
- Notifications
- Reports and dashboards
- Organizations, branches and staff
- Audit logs

Use explicit schemas for create, update, list and response operations. Validate filters and pagination parameters. Enforce permissions, tenant isolation and business rules inside the backend.

## 15. Security and Reliability

Implement:

- Secure password hashing
- Authentication and authorization checks
- Tenant isolation tests
- Input validation and safe upload handling
- CORS allowlists
- Rate limiting on sensitive routes
- Secure headers at the appropriate deployment layer
- Secret management through environment variables
- Database transaction boundaries
- Idempotency for payment webhooks and retry-sensitive operations
- Audit trails for sensitive changes
- Dependency and vulnerability checks
- Data backup and restore documentation
- Configurable log retention and privacy-conscious logging

Do not log passwords, tokens, payment credentials or unnecessary personal information.

## 16. Testing

Create meaningful automated tests for:

- Authentication and role permissions
- Member CRUD and search
- Membership expiry and renewal
- Attendance eligibility and duplicate prevention
- Billing totals, partial payments and refunds
- Concurrent or repeated payment callbacks
- Organization isolation
- Database migrations
- API validation and error handling
- Critical frontend workflows

Use isolated test configuration and test data. Do not run destructive integration tests against the user's development or production database.

## 17. Local Windows Setup

Provide:

- A complete requirements.txt
- package.json with working scripts
- Docker Compose for PostgreSQL
- .env.example files for frontend and backend
- Alembic migration commands
- Safe database initialization and demo seeding scripts
- A Windows start.bat script that starts the database and both applications where Docker is available
- Separate backend and frontend commands
- A health-check endpoint
- A troubleshooting guide for ports, dependencies, environment variables and database connection errors

Suggested local addresses:

- Frontend: http://localhost:5173
- Backend API: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- PostgreSQL: localhost:5432, accessible only as needed for local development

Use a development-only seeded administrator with instructions to change or disable demo credentials before deployment. Never seed default administrator credentials into a production environment.

## 18. Production Readiness

Provide:

- Separate development, test and production configurations
- Production Dockerfiles and deployment documentation
- Reverse-proxy and HTTPS guidance
- Secure production secret configuration
- Database migration and rollback strategy
- Backup and restore procedures
- Liveness and readiness health checks
- Structured logging and operational monitoring
- Static asset build and delivery configuration
- CI workflow for linting and tests
- Dependency locking and reproducible installation instructions
- Data retention and privacy documentation
- Deployment and incident troubleshooting runbooks

Do not claim production readiness until the relevant functionality, security checks, migrations, tests and deployment configuration have been verified.

## 19. Implementation Workflow

Work in these phases:

Phase 1: Architecture, repository structure, configuration and database connectivity.

Phase 2: Database models, migrations, authentication, authorization and tenant isolation.

Phase 3: Members, membership plans, renewals and attendance.

Phase 4: Trainers, workout plans, schedules and session management.

Phase 5: Billing, invoices, payments, refunds, expenses and inventory.

Phase 6: Dashboards, reports, notifications and audit trails.

Phase 7: Complete frontend integration and member portal.

Phase 8: Automated testing, performance optimization, security review and deployment documentation.

For each phase:

1. Create actual source files.
2. Implement working functionality.
3. Run relevant tests and static checks.
4. Fix errors before proceeding.
5. Document changed files, commands and configuration.
6. Never mark an incomplete feature as finished.

## Final Acceptance Criteria

The finished application must allow an administrator to sign in, create a branch, configure a membership plan, register a member, assign a membership, record a payment, issue a receipt, check in the member, track attendance, view dashboard metrics and export an authorized report.

All of these actions must persist in PostgreSQL and remain consistent after application restarts.

Provide the complete source code, local setup guide, environment examples, migrations, tests, demo data, Windows startup scripts and production deployment documentation.

Do not stop after generating the architecture or UI. Continue implementation until the acceptance criteria are verified, or clearly list what remains incomplete.