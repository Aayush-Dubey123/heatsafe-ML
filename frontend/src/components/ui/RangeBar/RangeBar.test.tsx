import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RangeBar } from "./RangeBar";

describe("RangeBar", () => {
  it("gives screen readers the value and range as a sentence", () => {
    render(<RangeBar value={32.7} low={31} high={34.5} />);
    expect(screen.getByRole("img", { name: /32\.7.*31\.0.*34\.5/ })).toBeInTheDocument();
  });
});
