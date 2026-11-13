import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { apiError, mockApi, renderWithProviders } from "../../../test/utils/test-utils";
import { HomePage } from "./HomePage";

describe("HomePage", () => {
  it("asks where you are before showing anything", () => {
    mockApi();
    renderWithProviders(<HomePage />);
    expect(screen.getByRole("heading", { name: "How hot is your area?" })).toBeInTheDocument();
    expect(screen.queryByText("Ground surface temperature")).not.toBeInTheDocument();
  });

  it("shows the answer and cooling places for a shared link", async () => {
    const { calls } = mockApi();
    renderWithProviders(<HomePage />, "/?lat=21.1458&lon=79.0882&name=Dhantoli");
    expect(await screen.findByText("33 °C")).toBeInTheDocument();
    expect(await screen.findByText("Dik Hospital")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Dhantoli" })).toBeInTheDocument();
    expect(calls.some((c) => c.startsWith("/heat?lat=21.1458"))).toBe(true);
  });

  it("puts the chosen place in the URL after searching", async () => {
    mockApi();
    renderWithProviders(<HomePage />);
    await userEvent.type(screen.getByRole("combobox"), "ajni");
    await userEvent.click(await screen.findByRole("option", { name: /Ajni/ }));
    expect(await screen.findByText("33 °C")).toBeInTheDocument();
    expect(screen.getByTestId("location").textContent).toMatch(/lat=21\.\d+&lon=79\.\d+&name=Ajni/);
  });

  it("explains a spot outside the study area", async () => {
    mockApi({ "/heat": apiError(422, "outside_study_area", "outside") });
    renderWithProviders(<HomePage />, "/?lat=21.1458&lon=79.0882");
    expect(await screen.findByText("That place is outside the Nagpur study area.")).toBeInTheDocument();
  });

  it("offers a retry after a network failure", { timeout: 15000 }, async () => {
    mockApi({
      "/heat": () => {
        throw new TypeError("offline");
      },
    });
    renderWithProviders(<HomePage />, "/?lat=21.1458&lon=79.0882");
    expect(await screen.findByText(/could not reach the service/, {}, { timeout: 8000 })).toBeInTheDocument(); // retries twice first
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
