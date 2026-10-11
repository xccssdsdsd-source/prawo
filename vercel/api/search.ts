import { route, param, parseLimit } from '../lib/http';
import { searchLaw } from '../lib/law';

export default route({ auth: true, scope: 'search', rateLimit: 60, sMaxAge: 300 }, (req) =>
  searchLaw({
    q: param(req, 'q'),
    kategoria: param(req, 'kategoria'),
    act: param(req, 'act'),
    limit: parseLimit(param(req, 'limit')),
  }),
);
