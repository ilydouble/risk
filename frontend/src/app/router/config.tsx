import { lazy, Suspense, type ReactNode } from "react";
import type { RouteObject } from "react-router-dom";
import AppLayout from "@/app/layout/AppLayout";
import AuthGate from "@/app/router/AuthGate";
import NotFound from "@/pages/NotFound";

const Overview = lazy(() => import("@/pages/overview/page"));
const SearchPage = lazy(() => import("@/pages/search/page"));
const CompanyPage = lazy(() => import("@/pages/company/page"));
const GraphPage = lazy(() => import("@/pages/graph/page"));
const ScorePage = lazy(() => import("@/pages/score/page"));
const ReportPage = lazy(() => import("@/pages/report/page"));
const DecisionPage = lazy(() => import("@/pages/decision/page"));
const ModelPage = lazy(() => import("@/pages/model/page"));
const ModelArchivePage = lazy(() => import("@/pages/model/archive/page"));
const BatchPage = lazy(() => import("@/pages/batch/page"));
const LoginPage = lazy(() => import("@/pages/login/page"));
const RegisterPage = lazy(() => import("@/pages/register/page"));

function load(page: ReactNode) {
  return <Suspense fallback={<div className="py-10 text-center text-sm text-foreground-500">正在加载…</div>}>{page}</Suspense>;
}

const routes: RouteObject[] = [
  { path: "/login", element: load(<LoginPage />) },
  { path: "/register", element: load(<RegisterPage />) },
  {
    element: <AuthGate />,
    children: [{
      element: <AppLayout />,
      children: [
        { path: "/", element: load(<Overview />) },
        { path: "/search", element: load(<SearchPage />) },
        { path: "/company/:id", element: load(<CompanyPage />) },
        { path: "/graph", element: load(<GraphPage />) },
        { path: "/score/:id", element: load(<ScorePage />) },
        { path: "/report/:id", element: load(<ReportPage />) },
        { path: "/decision/:id", element: load(<DecisionPage />) },
        { path: "/model-card", element: load(<ModelArchivePage />) },
        { path: "/model", element: load(<ModelPage />) },
        { path: "/batch", element: load(<BatchPage />) },
        { path: "*", element: <NotFound /> },
      ],
    }],
  },
];

export default routes;
