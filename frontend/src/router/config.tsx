import type { RouteObject } from "react-router-dom";
import NotFound from "../pages/NotFound";
import Overview from "../pages/overview/page";
import SearchPage from "../pages/search/page";
import CompanyPage from "../pages/company/page";
import GraphPage from "../pages/graph/page";
import ScorePage from "../pages/score/page";
import ReportPage from "../pages/report/page";
import DecisionPage from "../pages/decision/page";
import ModelPage from "../pages/model/page";
import ModelArchivePage from "../pages/model/archive/page";
import BatchPage from "../pages/batch/page";

const routes: RouteObject[] = [
  {
    path: "/",
    element: <Overview />,
  },
  {
    path: "/search",
    element: <SearchPage />,
  },
  {
    path: "/company/:id",
    element: <CompanyPage />,
  },
  {
    path: "/graph",
    element: <GraphPage />,
  },
  {
    path: "/score/:id",
    element: <ScorePage />,
  },
  {
    path: "/report/:id",
    element: <ReportPage />,
  },
  {
    path: "/decision/:id",
    element: <DecisionPage />,
  },
  {
    path: "/model-card",
    element: <ModelArchivePage />,
  },
  {
    path: "/model",
    element: <ModelPage />,
  },
  {
    path: "/batch",
    element: <BatchPage />,
  },
  {
    path: "*",
    element: <NotFound />,
  },
];

export default routes;