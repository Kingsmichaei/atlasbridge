import { lazy, Suspense, type ReactNode } from "react";
import { Link, Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import { RequireAuth } from "./lib/auth";
import Landing from "./pages/Landing";
import { Login, Signup } from "./pages/Auth";
import DashboardLayout from "./pages/dashboard/DashboardLayout";

// Loaded on demand so the landing page stays small on mobile data (Recharts alone is ~400 kB).
const Guide = lazy(() => import("./pages/Guide"));
const Playground = lazy(() => import("./pages/Playground"));
const Overview = lazy(() => import("./pages/dashboard/Overview"));
const Keys = lazy(() => import("./pages/dashboard/Keys"));
const UsagePage = lazy(() => import("./pages/dashboard/Usage"));
const Settings = lazy(() => import("./pages/dashboard/Settings"));

const Page = ({ children }: { children: ReactNode }) => (
  <Suspense fallback={<div className="container-x py-20 text-center text-muted">Loading…</div>}>{children}</Suspense>
);

function NotFound() {
  return (
    <div className="container-x py-24 text-center">
      <h1 className="text-2xl font-bold">Page not found</h1>
      <p className="mt-2 text-muted">That page doesn't exist.</p>
      <Link to="/" className="btn btn-primary mt-6">Go home</Link>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Landing />} />
        <Route path="login" element={<Login />} />
        <Route path="signup" element={<Signup />} />
        <Route path="guide" element={<Page><Guide /></Page>} />
        <Route path="playground" element={<RequireAuth><Page><Playground /></Page></RequireAuth>} />
        <Route path="dashboard" element={<RequireAuth><DashboardLayout /></RequireAuth>}>
          <Route index element={<Page><Overview /></Page>} />
          <Route path="keys" element={<Page><Keys /></Page>} />
          <Route path="usage" element={<Page><UsagePage /></Page>} />
          <Route path="settings" element={<Page><Settings /></Page>} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
