import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ZoomDock, zoomBand } from "./ZoomDock";
import type { ZoomableMap } from "./ZoomDock";

function fakeMap(zoom = 12): ZoomableMap {
  return {
    getZoom: () => zoom,
    zoomTo: vi.fn(),
    zoomIn: vi.fn(),
    zoomOut: vi.fn(),
    fitBounds: vi.fn(),
    flyTo: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
  };
}
const bounds: [number, number, number, number] = [78.9, 21.0, 79.2, 21.25];

describe("zoomBand", () => {
  it("names how close the map is", () => {
    expect([10, 12, 15].map(zoomBand)).toEqual(["zoomCity", "zoomArea", "zoomStreet"]);
  });
});

describe("ZoomDock", () => {
  it("zooms with the buttons", async () => {
    const map = fakeMap();
    render(<ZoomDock map={map} bounds={bounds} />);
    await userEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    await userEvent.click(screen.getByRole("button", { name: "Zoom out" }));
    expect(map.zoomIn).toHaveBeenCalledTimes(1);
    expect(map.zoomOut).toHaveBeenCalledTimes(1);
  });

  it("moves the map live from the slider and names the level", () => {
    const map = fakeMap(12);
    render(<ZoomDock map={map} bounds={bounds} />);
    const slider = screen.getByRole("slider", { name: "Zoom" });
    expect(slider).toHaveAttribute("aria-valuetext", "Area");
    fireEvent.change(slider, { target: { value: "15" } });
    expect(map.zoomTo).toHaveBeenCalledWith(15, { duration: 0 });
  });

  it("jumps to the whole city and to the selected spot", async () => {
    const map = fakeMap();
    render(<ZoomDock map={map} bounds={bounds} spot={{ lat: 21.14, lon: 79.08 }} />);
    await userEvent.click(screen.getByRole("button", { name: "Show whole city" }));
    expect(map.fitBounds).toHaveBeenCalledWith(bounds, { padding: 16 });
    await userEvent.click(screen.getByRole("button", { name: "Zoom to selected spot" }));
    expect(map.flyTo).toHaveBeenCalledWith({ center: [79.08, 21.14], zoom: 15 });
  });

  it("hides the spot jump when nothing is selected and disables plus at max zoom", () => {
    render(<ZoomDock map={fakeMap(17)} bounds={bounds} />);
    expect(screen.queryByRole("button", { name: "Zoom to selected spot" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zoom in" })).toBeDisabled();
  });
});
