import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { afterEach, describe, it, expect, vi } from "vitest";
import { Form, Table, Modal } from "./ui";
afterEach(cleanup);
describe("working forms", () => {
  it("preserves exact decimal input and displays backend errors without success", async () => {
    const submit = vi
      .fn()
      .mockRejectedValue(new Error("Payment exceeds outstanding balance"));
    const done = vi.fn();
    render(
      <Form
        fields={[
          { name: "amount", label: "Amount", type: "money", required: true },
        ]}
        submit={submit}
        onDone={done}
      />,
    );
    fireEvent.change(screen.getByLabelText(/Amount/), {
      target: { value: "10.05" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Payment exceeds outstanding balance");
    expect(submit).toHaveBeenCalledWith(
      { amount: "10.05" },
      expect.any(String),
    );
    expect(done).not.toHaveBeenCalled();
  });
  it("submits checkbox and numeric inputs as typed values", async () => {
    const submit = vi.fn().mockResolvedValue({});
    render(
      <Form
        fields={[
          { name: "days", label: "Days", type: "number", defaultValue: 30 },
          {
            name: "active",
            label: "Active",
            type: "checkbox",
            defaultValue: true,
          },
        ]}
        submit={submit}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith(
        { days: 30, active: true },
        expect.any(String),
      ),
    );
  });
  it("reuses the request key after failure and changes it for edited input", async () => {
    const submit = vi
      .fn()
      .mockRejectedValue(new Error("Connection interrupted"));
    render(
      <Form
        fields={[
          {
            name: "amount",
            label: "Amount",
            type: "money",
            defaultValue: "10.05",
          },
        ]}
        submit={submit}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Connection interrupted");
    const firstKey = submit.mock.calls[0][1];
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Connection interrupted");
    expect(submit.mock.calls[1][1]).toBe(firstKey);
    fireEvent.change(screen.getByLabelText(/Amount/), {
      target: { value: "20.10" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Connection interrupted");
    expect(submit.mock.calls[2][1]).not.toBe(firstKey);
  });
  it("paginates tables and keeps previous disabled on page one", () => {
    const onPage = vi.fn();
    render(
      <Table
        data={{
          items: [{ id: "1", name: "Alex" }],
          total: 50,
          page: 1,
          size: 25,
        }}
        columns={[{ key: "name", label: "Member" }]}
        onPage={onPage}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Previous page" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(onPage).toHaveBeenCalledWith(2);
  });
  it("shows a meaningful empty state", () => {
    render(<Table data={[]} columns={[]} />);
    expect(screen.getByText(/No records yet/)).toBeVisible();
  });
});
