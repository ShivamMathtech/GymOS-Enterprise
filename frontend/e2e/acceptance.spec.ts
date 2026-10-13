import { test, expect } from "@playwright/test";
test("owner creates member, purchases membership, records payment and checks in", async ({
  page,
}) => {
  const suffix = Date.now().toString();
  await page.goto("/login");
  await page.getByRole("button", { name: /Create a workspace/ }).click();
  await page.getByLabel(/Gym \/ organization name/).fill("E2E Fitness");
  await page
    .getByLabel("Organization ID", { exact: false })
    .fill("e2e-" + suffix);
  await page.getByLabel("Your name").fill("QA Owner");
  await page
    .getByLabel("Email", { exact: false })
    .fill("owner-" + suffix + "@example.com");
  await page
    .getByLabel("Password", { exact: false })
    .fill("E2E-password-strong-42");
  await page.getByRole("button", { name: /Create workspace →/ }).click();
  await expect(
    page.getByRole("heading", { name: /Good to see you/ }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Team & settings" }).click();
  await page.getByRole("button", { name: "Add branch" }).click();
  await page.getByLabel("Branch name", { exact: false }).fill("Main");
  await page.getByLabel("Opens", { exact: false }).fill("00:00");
  await page.getByLabel("Closes", { exact: false }).fill("00:00");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("link", { name: "Members", exact: true }).click();
  await page.getByRole("button", { name: "Register member" }).click();
  await page
    .getByLabel("Home branch", { exact: false })
    .selectOption({ label: "Main" });
  await page.getByLabel("Full name", { exact: false }).fill("Jamie Test");
  await page.getByLabel("Phone", { exact: false }).fill("9876543210");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Jamie Test", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Memberships", exact: true }).click();
  await page.getByRole("button", { name: "Create plan" }).click();
  await page.getByLabel("Plan name", { exact: false }).fill("Monthly");
  await page.getByLabel("Price").fill("1000");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "Assign membership" }).click();
  await page
    .getByLabel("Member", { exact: false })
    .first()
    .selectOption({ label: "Jamie Test" });
  await page
    .getByLabel("Plan", { exact: false })
    .selectOption({ label: "Monthly" });
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("pending payment")).toBeVisible();
  await page.getByRole("link", { name: "Billing & payments" }).click();
  await page
    .getByRole("button", { name: "Record payment", exact: true })
    .click();
  await page.getByLabel("Method", { exact: false }).selectOption("cash");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("paid", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Attendance", exact: true }).click();
  await page
    .getByRole("button", { name: "Check in member", exact: false })
    .click();
  await page
    .getByLabel("Member", { exact: false })
    .selectOption({ label: "Jamie Test" });
  await page
    .getByLabel("Check-in branch", { exact: false })
    .selectOption({ label: "Main" });
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Check out", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText("Jamie Test", { exact: true })).toBeVisible();
});
