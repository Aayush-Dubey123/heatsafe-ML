import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { mockApi, renderWithProviders } from "../../../test/utils/test-utils";
import { LocationPicker } from "./LocationPicker";

describe("LocationPicker", () => {
  it("searches locality names and reports the chosen place", async () => {
    mockApi();
    const onPick = vi.fn();
    renderWithProviders(<LocationPicker onPick={onPick} />);
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    await userEvent.type(screen.getByRole("combobox"), "dhan");
    await userEvent.click(await screen.findByRole("option", { name: /Dhantoli/ }));
    expect(onPick).toHaveBeenCalledTimes(1);
    const [lat, lon, name] = onPick.mock.calls[0] as [number, number, string];
    expect(name).toBe("Dhantoli");
    expect(lat).toBeCloseTo(21.14, 2);
    expect(lon).toBeCloseTo(79.08, 2);
  });

  it("says so when nothing matches", async () => {
    mockApi();
    renderWithProviders(<LocationPicker onPick={vi.fn()} />);
    await userEvent.type(screen.getByRole("combobox"), "zzz");
    expect(await screen.findByText(/No locality matches/)).toBeInTheDocument();
  });

  it("supports the keyboard", async () => {
    mockApi();
    const onPick = vi.fn();
    renderWithProviders(<LocationPicker onPick={onPick} />);
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    await userEvent.type(screen.getByRole("combobox"), "a");
    await screen.findAllByRole("option");
    await userEvent.keyboard("{Enter}");
    expect(onPick).toHaveBeenCalledTimes(1);
  });

  it("shows a helpful message when location access is denied", async () => {
    mockApi();
    const denied = { PERMISSION_DENIED: 1, code: 1 };
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: { getCurrentPosition: (_ok: unknown, fail: (e: unknown) => void) => fail(denied) },
    });
    renderWithProviders(<LocationPicker onPick={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Use my location/ }));
    expect(await screen.findByText(/Location access is blocked/)).toBeInTheDocument();
  });
});
