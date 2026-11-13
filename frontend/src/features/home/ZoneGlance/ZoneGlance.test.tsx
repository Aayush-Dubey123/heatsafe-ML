import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { mockApi, renderWithProviders } from "../../../test/utils/test-utils";
import { ZoneGlance } from "./ZoneGlance";

describe("ZoneGlance", () => {
  it("shows the highest-risk zones and opens the Zones page on one", async () => {
    mockApi();
    renderWithProviders(<ZoneGlance />);
    const button = await screen.findByRole("button", { name: "Gandhibagh" });
    await userEvent.click(button);
    expect(screen.getByTestId("location").textContent).toBe("/zones?zone=1");
    expect(screen.getByRole("link", { name: "See all zones" })).toHaveAttribute("href", "/zones");
  });
});
