import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { product } from "../../../test/fixtures/fixtures";
import { FreshnessBanner } from "./FreshnessBanner";

describe("FreshnessBanner", () => {
  it("renders nothing for fresh data", () => {
    const { container } = render(<FreshnessBanner product={product} offline={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("warns when the data is stale and states the limit", () => {
    render(<FreshnessBanner product={{ ...product, stale: true, scene_age_days: 20 }} offline={false} />);
    expect(screen.getByRole("status")).toHaveTextContent("20 days old (limit 16 days)");
  });

  it("says when offline, and when nothing is published", () => {
    const { rerender } = render(<FreshnessBanner offline />);
    expect(screen.getByRole("status")).toHaveTextContent(/offline/i);
    rerender(<FreshnessBanner offline={false} noProduct />);
    expect(screen.getByRole("status")).toHaveTextContent(/No heat data is published/);
  });
});
