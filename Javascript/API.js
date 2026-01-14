require('dotenv').config();

const API_KEY = process.env.API_KEY;
const DOMAIN_URL = process.env.DOMAIN_URL;

if (!API_KEY) {
  console.error('Missing API_KEY in environment. Please set API_KEY in your .env file.');
  process.exit(1);
}

if (!DOMAIN_URL) {
  console.error('Missing DOMAIN_URL in environment. Please set DOMAIN_URL in your .env file.');
  process.exit(1);
}

/**
 * Request options used for TOD Markets API calls.
 * @type {RequestInit & { headers: Record<string,string> }}
 */
const requestOptions = {
  method: 'GET',
  redirect: 'follow',
  headers: {
    'Authorization': `Bearer ${API_KEY}`,
    'Content-Type': 'application/json'
  }
};

/**
 * Fetches from a TOD Markets endpoint and returns the response body as text.
 *
 * @param {string} endpoint - Path of the endpoint to call (e.g. '/company' or 'company').
 * @param {{[key: string]: string|number|boolean|Array<string|number|boolean>}|string|URLSearchParams} [parameters]
 *   Query parameters to append to the URL. Can be an object (values may be arrays to repeat keys),
 *   a query string (e.g. '?limit=10'), or a URLSearchParams instance.
 * @returns {Promise<string>} Resolves with the response body text.
 * @throws {TypeError} If `parameters` is not an object, string, or URLSearchParams.
 * @throws {Error} If the HTTP response status is not ok (non-2xx).
 *
 * @example
 * // Object parameters
 * await getTodMarketsEndpoint('/company', { limit: 10, filter: 'active' });
 *
 * @example
 * // Query string
 * await getTodMarketsEndpoint('/company', '?limit=10&filter=active');
 */
const getTodMarketsEndpoint = async (endpoint, parameters) => {
  // Build the full URL from DOMAIN_URL + endpoint
  const url = new URL(endpoint, DOMAIN_URL);

  // Append query parameters if provided. Accepts object, string, or URLSearchParams
  if (parameters) {
    if (parameters instanceof URLSearchParams) {
      for (const [k, v] of parameters.entries()) url.searchParams.append(k, v);
    } else if (typeof parameters === 'object') {
      Object.entries(parameters).forEach(([k, v]) => {
        if (v === undefined || v === null) return;
        if (Array.isArray(v)) v.forEach(val => url.searchParams.append(k, String(val)));
        else url.searchParams.append(k, String(v));
      });
    } else if (typeof parameters === 'string') {
      const qs = parameters.startsWith('?') ? parameters.slice(1) : parameters;
      const sp = new URLSearchParams(qs);
      for (const [k, v] of sp.entries()) url.searchParams.append(k, v);
    } else {
      throw new TypeError('parameters must be an object, string, or URLSearchParams');
    }
  }
  // make the request
  console.log(`Fetching: ${url.toString()}`);
  const res = await fetch(url.toString(), requestOptions);
  if (!res.ok) throw new Error(`Request failed: ${res.status} ${res.statusText}`);
  return await res.text(); // returns the response body to callers
};

/**
 * POSTs JSON payload to a TOD Markets endpoint and returns the response body as text.
 *
 * @param {string} endpoint - Path of the endpoint to call (e.g. '/company').
 * @param {any} [payload={}] - JSON-serializable payload to send as the request body.
 * @returns {Promise<string>} Resolves with the response body text.
 * @throws {Error} If the HTTP response status is not ok (non-2xx).
 *
 * @example
 * await postTodMarketsEndpoint('/company', { name: 'Acme', active: true });
 */
const postTodMarketsEndpoint = async (endpoint, payload = {}) => {
  const url = new URL(endpoint, DOMAIN_URL);

  // Stringify payload; let JSON.stringify handle any serialization rules
  const body = JSON.stringify(payload);

  const opts = {
    ...requestOptions,
    method: 'POST',
    headers: {
      ...requestOptions.headers,
      'Content-Type': 'application/json'
    },
    body
  };

  const res = await fetch(url.toString(), opts);
  if (!res.ok) throw new Error(`Request failed: ${res.status} ${res.statusText}`);
  return await res.text();
};

if (require.main === module) {
  // include leading slash if your endpoints expect it and pass query params as second arg
  getTodMarketsEndpoint('/api/assets/prices', { markets: 'N Q', periods: 'Q326', bucket: 'EP MD' }).then(console.log).catch(console.error);
  // Example POST call (will print response body)
  postTodMarketsEndpoint('/api/order',
    {
      "asset_code": "Q-Q127C6X",
      "type": "BUY",
      "price": 10.66,
      "quantity": 10,
      "replace_match": true,
      "is_persistent": false,
      "status" : "HOLD"
    }
  ).then(console.log).catch(console.error);
}

exports.getTodMarketsEndpoint = getTodMarketsEndpoint;
exports.postTodMarketsEndpoint = postTodMarketsEndpoint;

