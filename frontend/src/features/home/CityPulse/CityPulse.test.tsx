import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { mockApi, renderWithProviders } from "../../../test/utils/test-utils";
import { CityPulse } from "./CityPulse";

describe("CityPulse", () => {
  it("lists the hottest and coolest localities and picks one on tap", async () => {
    mockApi();
    const onPick = vi.fn();
    renderWithProviders(<CityPulse onPick={onPick} />);
    const hottest = (await screen.findByRole("heading", { name: "Hottest localities" })).parentElement as HTMLElement;
    const first = within(hottest).getAllByRole("button")[0] as HTMLElement;
    expect(first).toHaveTextContent("Ajni");
    expect(first).toHaveTextContent("46.0 °C");
    await userEvent.click(first);
    expect(onPick).toHaveBeenCalledWith(expect.any(Number), expect.any(Number), "Ajni");
    const coolest = screen.getByRole("heading", { name: "Coolest localities" }).parentElement as HTMLElement;
    expect(within(coolest).getAllByRole("button")[0]).toHaveTextContent("Dhantoli");
  });
});
