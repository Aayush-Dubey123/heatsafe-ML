import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Tabs } from "./Tabs";

const tabs = [
  { id: "a", label: "First", content: <p>Panel A</p> },
  { id: "b", label: "Second", content: <p>Panel B</p> },
  { id: "c", label: "Third", content: <p>Panel C</p> },
];

describe("Tabs", () => {
  it("shows one panel at a time and switches on click", async () => {
    render(<Tabs tabs={tabs} label="Demo" />);
    expect(screen.getByText("Panel A")).toBeInTheDocument();
    expect(screen.queryByText("Panel B")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Second" }));
    expect(screen.getByText("Panel B")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Second" })).toHaveAttribute("aria-selected", "true");
  });

  it("moves with the arrow keys, wrapping around", async () => {
    render(<Tabs tabs={tabs} label="Demo" />);
    screen.getByRole("tab", { name: "First" }).focus();
    await userEvent.keyboard("{ArrowLeft}");
    expect(screen.getByText("Panel C")).toBeInTheDocument();
    await userEvent.keyboard("{Home}");
    expect(screen.getByText("Panel A")).toBeInTheDocument();
  });

  it("can be controlled", async () => {
    const seen: string[] = [];
    render(<Tabs tabs={tabs} label="Demo" value="b" onChange={(id) => seen.push(id)} />);
    expect(screen.getByText("Panel B")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Third" }));
    expect(seen).toEqual(["c"]);
  });
});
