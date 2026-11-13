import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { heat } from "../../../test/fixtures/fixtures";
import { mockApi, renderWithProviders } from "../../../test/utils/test-utils";
import { AdviceHero, adviceKey } from "./AdviceHero";

describe("adviceKey", () => {
  it("bands the ground temperature", () => {
    expect([25, 33, 40, 50].map(adviceKey)).toEqual(["mild", "warm", "hot", "veryHot"]);
  });
});

describe("AdviceHero", () => {
  it("shows a plain headline, the temperature and the nearest cool place with directions", async () => {
    mockApi();
    renderWithProviders(<AdviceHero heat={heat} place="Dhantoli" />);
    expect(screen.getByRole("heading", { name: "The ground is warm right now" })).toBeInTheDocument();
    expect(screen.getByText("33 °C")).toBeInTheDocument();
    expect(await screen.findByText(/Nearest cool place: Drinking water \(unnamed\), 440 m away/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Directions/ });
    expect(link).toHaveAttribute("href", expect.stringContaining("google.com/maps/dir"));
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("renders nothing for a spot without an estimate", () => {
    mockApi();
    const { container } = renderWithProviders(<AdviceHero heat={{ ...heat, covered: false, lst_celsius: null }} />);
    expect(container.querySelector("section")).toBeNull();
  });
});
