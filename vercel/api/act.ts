import { route, param } from '../lib/http';
import { getAct } from '../lib/law';

export default route({ auth: true, scope: 'act', rateLimit: 120, sMaxAge: 3600 }, (req) =>
  getAct({
    id: param(req, 'id'),
    variant: param(req, 'variant'),
    include_toc: ['1', 'true'].includes(param(req, 'include_toc') ?? ''),
  }),
);
