import { route, param } from '../lib/http';
import { getArticle } from '../lib/law';

export default route({ auth: true, scope: 'article', rateLimit: 120, sMaxAge: 3600 }, (req) =>
  getArticle({ id: param(req, 'id'), art: param(req, 'art'), variant: param(req, 'variant') }),
);
