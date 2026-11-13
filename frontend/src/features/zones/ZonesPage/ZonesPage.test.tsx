import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { mockApi, renderWithProviders } from "../../../test/utils/test-utils";
import { ZonesPage } from "./ZonesPage";

describe("ZonesPage", () => {
  it("ranks zones by risk with the rank interval and the approximation notice", async () => {
    mockApi();
    renderWithProviders(<ZonesPage />);
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((r) => within(r).getByRole("button").textContent)).toEqual(["Gandhibagh", "Satranjipura", "Mangalwari"]);
    expect(within(rows[0] as HTMLElement).getByText("1 [1–2]")).toBeInTheDocument();
    expect(screen.getByText(/approximate/)).toBeInTheDocument();
  });

  it("re-sorts by exposure", async () => {
    mockApi();
    renderWithProviders(<ZonesPage />);
    await screen.findByRole("table");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: /Rank by/ }), "exposure");
    const first = within(screen.getByRole("table")).getAllByRole("row")[1] as HTMLElement;
    expect(within(first).getByRole("button").textContent).toBe("Mangalwari");
  });

  it("shows details and keeps the selection in the URL", async () => {
    mockApi();
    renderWithProviders(<ZonesPage />);
    const buttons = await screen.findAllByRole("button", { name: "Satranjipura" });
    await userEvent.click(buttons[0] as HTMLElement);
    expect(await screen.findByRole("heading", { name: "Satranjipura" })).toBeInTheDocument();
    expect(screen.getByText(/Aged 60\+ share/)).toBeInTheDocument();
    expect(screen.getByTestId("location").textContent).toContain("zone=2");
  });

  it("switches to localities", async () => {
    mockApi();
    renderWithProviders(<ZonesPage />);
    await userEvent.click(screen.getByRole("button", { name: "Localities" }));
    expect(await screen.findByText("Hudkeshwar")).toBeInTheDocument();
  });
});
