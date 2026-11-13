import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { heat } from "../../../test/fixtures/fixtures";
import { HeatCard } from "./HeatCard";

describe("HeatCard", () => {
  it("shows the rounded estimate, range, observed badge and the surface-temperature caveat", () => {
    render(<HeatCard heat={heat} />);
    expect(screen.getByText("33 °C")).toBeInTheDocument();
    expect(screen.getByText("likely 31 to 35")).toBeInTheDocument();
    expect(screen.getByText("Seen by satellite")).toBeInTheDocument();
    expect(screen.getByText(/not the air temperature/)).toBeInTheDocument();
    expect(screen.getByText(/hotter than about 58%/)).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("flags model-filled values and explains them", () => {
    render(<HeatCard heat={{ ...heat, observed: false }} />);
    expect(screen.getByText("Estimated by model")).toBeInTheDocument();
    expect(screen.getByText(/comes from the model and is less certain/)).toBeInTheDocument();
  });

  it("explains uncovered spots instead of showing a number", () => {
    render(<HeatCard heat={{ ...heat, covered: false, lst_celsius: null, lst_p05: null, lst_p95: null }} />);
    expect(screen.getByRole("status")).toHaveTextContent(/No estimate for this spot/);
    expect(screen.queryByText(/°C$/)).not.toBeInTheDocument();
  });

  it("hides the seasonal table in compact mode", () => {
    render(<HeatCard heat={heat} compact />);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
