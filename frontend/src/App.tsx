import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/layout/Shell/Shell";
import { ErrorBoundary } from "./components/status/ErrorBoundary/ErrorBoundary";
import { LoadingBlock } from "./components/status/StateViews/StateViews";
import { AboutPage } from "./features/about/AboutPage/AboutPage";
import { HomePage } from "./features/home/HomePage/HomePage";

// The map library is large: load it (and the zones page) only when someone opens those tabs.
const MapPage = lazy(() => import("./features/map/MapPage/MapPage").then((m) => ({ default: m.MapPage })));
const ZonesPage = lazy(() => import("./features/zones/ZonesPage/ZonesPage").then((m) => ({ default: m.ZonesPage })));

/** Routes: Home (answer first), Map, Zones (planner view), About. Unknown paths go home. */
export function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<div className="page"><LoadingBlock lines={4} /></div>}>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<HomePage />} />
            <Route path="map" element={<MapPage />} />
            <Route path="zones" element={<ZonesPage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}
