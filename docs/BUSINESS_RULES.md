# Business rules and metric definitions

## Membership lifecycle

Dates are inclusive at start and exclusive at end. Status is evaluated in the membership's branch-local calendar:

1. Cancelled → cancelled.
2. Unpaid balance → pending_payment.
3. Today before start → scheduled.
4. Today inside freeze interval → frozen.
5. Today at/after end → expired, or grace if within the branch grace period.
6. Otherwise → active.

Profiles separately have active/inactive/archived status. Only active profiles can check in. An eligible membership must cover the check-in branch, either by home branch or an all-branches plan snapshot. Membership access is activated on full net payment; a refund that reopens a balance suspends access. Zero-total memberships activate without payment.

Plans use configured fixed day counts. Invoice price/tax and all-branch access are snapshotted when purchased. Renewal starts at the later of today and the latest non-cancelled membership end date. Renewing into a different plan implements an upgrade/downgrade at the next term boundary. No proration is implied.

Freeze begins today, requires active access and adds the frozen days to the end date. Extension and freeze refuse to overlap another non-cancelled membership, including a pending future term. Cancel is explicit and does not silently delete or refund an invoice.

## Money

Decimal and PostgreSQL NUMERIC perform every financial calculation. For each invoice line: subtotal = quantity × unit price − fixed discount; tax = subtotal × tax percentage / 100 rounded to two places with ROUND_HALF_UP; total = subtotal + tax. Each line rounds independently. Invoice total sums rounded line totals.

Net paid = recorded payments − recorded refunds. Outstanding = max(invoice total − net paid, 0), unless the invoice has been explicitly cancelled. Overpayment and over-refund are rejected. Cancel an invoice only when net paid is zero. Invoice cancellation also cancels linked access.

The organization currency is INR in this release. Currency is immutable through normal settings to avoid mixing currencies on historical records. Supporting another currency requires setting it at organization provisioning before transactions are created.

Cash, UPI, card, bank transfer and other are manual recording methods. GymOS does not collect money, verify a bank transfer or accept payment gateway callbacks. A staff member must independently confirm receipt before recording it. Receipts identify the immutable payment UUID and invoice number.

Payment, refund, membership assignment and renewal forms reuse their request key when an unchanged submission is retried after an error in the same open form. Editing the values or reopening the form starts a new request. After an uncertain network result, inspect the invoice or membership history before changing values or reopening the form to avoid recording the same business action again.

## Dashboard/report metrics

| Metric | Calculation |
|---|---|
| Total members | All non-deleted member profiles in permitted branches, including inactive/archived |
| Active members | Active profiles with at least one currently active paid membership; frozen, pending, grace and scheduled are excluded |
| Expired members | Members with an expired paid membership and no currently active membership; may also have future/pending terms |
| New members | Profiles created inside selected reporting interval |
| Today's attendance | Number of check-in records in the selected branch/organization-local day, including repeat completed visits |
| Period attendance | Check-in records in the selected date interval |
| Cash collected | Gross manually recorded payments whose recorded timestamps fall in the period |
| Refunds | Refund records timestamped in the period, regardless of original payment date |
| Net cash collected | Cash collected − refunds |
| Outstanding | Current all-time uncancelled invoice balances in permitted branches |
| Invoiced total | Uncancelled invoice totals created in the period; not recognized revenue |
| Expenses | Expense records whose expense date falls in the period |
| Retention cohort | Distinct members with a paid membership spanning the period start and beginning before it; reflects current cancellation/payment state |
| Retention | Cohort members who are currently active / cohort size; null for an empty cohort |
| Churn | Cohort members who are not currently active / cohort size; a snapshot proxy, not a historical cancellation rate |
| Expiring | Paid membership end dates from today through seven days ahead |
| Trainer workload | Sessions starting in period, including cancelled sessions in total; completed counted separately |
| Low stock | Stock ≤ configured low-stock level |
| Maintenance due | Non-retired equipment whose next-service date ≤ today |

Report end dates are exclusive. Range is limited to 366 days. Report date grouping uses the chosen branch time zone, or the organization time zone when consolidating branches. Browser tables show timestamps in the browser's local time. UTC instants remain authoritative in storage.

## Training

Availability is a same-day local time range plus weekdays (Monday=0). Booked sessions are 5–240 minutes, future-dated, within trainer availability, and cannot overlap another booked session for the member or trainer. Completed/no-show attendance is recorded after the scheduled end. Only booked sessions can be rescheduled or cancelled. Session packages are finite credits: booked/completed/no-show reserve or consume a credit; cancelled releases it.

## CSV and uploads

CSV duplicate checks normalize spaces/hyphens out of phone numbers. CSV error responses identify the source row; no rows import on validation failure. Export protects spreadsheet users against formula injection by prefixing formula-leading text.

Photos accept JPEG/PNG/WebP up to 3 MB and 12 megapixels, decode and re-encode as stripped JPEGs, use random server filenames, and are served only after authorization. Uploads are never served as an unauthenticated static directory.
