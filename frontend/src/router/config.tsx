import type { RouteObject } from 'react-router-dom';
import NotFound from '../pages/NotFound';
import { Overview, Search, Company, Score, GraphPage, Model, Unavailable } from '../live/pages';

const routes: RouteObject[] = [
  { path: '/', element: <Overview/> },
  { path: '/search', element: <Search/> },
  { path: '/company/:id', element: <Company/> },
  { path: '/score/:id', element: <Score/> },
  { path: '/graph', element: <GraphPage/> },
  { path: '/model', element: <Model/> },
  { path: '/model-card', element: <Model/> },
  { path: '/report/:id', element: <Unavailable/> },
  { path: '/decision/:id', element: <Unavailable/> },
  { path: '/batch', element: <Unavailable/> },
  { path: '*', element: <NotFound/> },
];
export default routes;
