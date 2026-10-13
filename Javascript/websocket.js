#!/usr/bin/env node
/**
 * JavaScript example for the TOD Markets private WebSocket connection.
 *
 * Install dependencies:
 *     npm install
 *
 * Usage:
 *     node Javascript/websocket.js
 *
 * TOD Markets publishes live updates through one of two services that both speak the Pusher protocol:
 * its own WebSocket server (Laravel Reverb, the primary) or Pusher (the fallback). GET /api/company names
 * the active one in `broadcast_driver`, so this script reads it before every connection and reconnects
 * whenever it changes.
 */
const WebSocket = require('ws');
const { getTodMarketsEndpoint } = require('./API.js');

const API_KEY = process.env.API_KEY;
const PLATFORM_URL = new URL(process.env.DOMAIN_URL).origin;

const CLIENT_NAME = 'tod-markets-js-example';
const CLIENT_VERSION = '2.0';
const SERVICE_CHECK_INTERVAL_MS = 5 * 60 * 1000;
const RECONNECT_DELAY_MS = 5 * 1000;

/**
 * Handlers for the events published on the private company channel, keyed by event name.
 */
const eventHandlers = {
  'App\\Events\\AssetPriceChangeEventCompany': (data) => console.log('[PRICE CHANGE]', data),
  'App\\Events\\OrderCreated': (data) => console.log('[ORDER CREATED]', data),
  'App\\Events\\OrderUpdated': (data) => console.log('[ORDER UPDATED]', data),
  'App\\Events\\OrderFilled': (data) => console.log('[ORDER FILLED]', data),
};

/**
 * Fetches the company's channel and WebSocket connection details from GET /api/company.
 *
 * @returns {Promise<object>} The `data` object of the response.
 */
const getConnectionDetails = async () => {
  const response = JSON.parse(await getTodMarketsEndpoint('/api/company'));
  return response.data;
};

/**
 * Returns the WebSocket URL of the service named by `broadcast_driver`.
 *
 * Reverb is used whenever the API names it. Pusher is used when the API names it, and also when the
 * field is absent, which is how a platform release from before Reverb answers.
 *
 * @param {object} details - The `data` object from GET /api/company.
 * @returns {{ service: string, url: string }}
 */
const endpointFor = (details) => {
  const query = `protocol=7&client=${CLIENT_NAME}&version=${CLIENT_VERSION}`;

  if (details.broadcast_driver === 'reverb') {
    const scheme = details.reverb_use_tls ? 'wss' : 'ws';
    return {
      service: 'reverb',
      url: `${scheme}://${details.reverb_host}:${details.reverb_port}/app/${details.reverb_key}?${query}`,
    };
  }

  return {
    service: 'pusher',
    url: `wss://ws-${details.pusher_cluster}.pusher.com:443/app/${details.pusher_key}?${query}`,
  };
};

/**
 * Asks the platform to authorise this socket to join a private channel.
 *
 * @param {string} socketId - The socket id from pusher:connection_established.
 * @param {string} channelName - The private channel, e.g. "private-company.abc123".
 * @returns {Promise<{ auth: string, channel_data?: string }>}
 */
const authoriseChannel = async (socketId, channelName) => {
  const response = await fetch(`${PLATFORM_URL}/api/broadcasting/auth`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ socket_id: socketId, channel_name: channelName }),
  });

  if (!response.ok) {
    throw new Error(`Channel authorisation failed: ${response.status} ${response.statusText}`);
  }

  return response.json();
};

/**
 * Parses a Pusher protocol `data` field, which arrives as a JSON-encoded string.
 *
 * @param {unknown} data
 * @returns {unknown}
 */
const parseEventData = (data) => {
  if (typeof data !== 'string') return data;
  try {
    return JSON.parse(data);
  } catch {
    return data;
  }
};

/**
 * Opens one connection to the active service, subscribes to the private company channel and resolves
 * once the socket closes for any reason.
 *
 * @param {object} details - The `data` object from GET /api/company.
 * @returns {{ closed: Promise<void>, close: () => void, service: string, channelName: string }}
 */
const openConnection = (details) => {
  const { service, url } = endpointFor(details);
  const channelName = `private-${details.channel_key}`;

  console.log(`Connecting to ${service}: ${url}`);

  // Reverb checks the Origin header against the platform's allowed origins, so send the platform's own address.
  const socket = new WebSocket(url, { origin: PLATFORM_URL });
  const send = (event, data = {}) => socket.send(JSON.stringify({ event, data }));

  // The server pings idle connections, so silence for longer than its activity timeout means the line is dead.
  let activityTimeout = 120;
  let watchdog = null;
  const resetWatchdog = (activityTimeoutSeconds) => {
    clearTimeout(watchdog);
    watchdog = setTimeout(() => {
      console.warn('No message within the activity timeout; reconnecting.');
      socket.terminate();
    }, (activityTimeoutSeconds + 30) * 1000);
  };
  socket.on('open', () => resetWatchdog(activityTimeout));

  socket.on('message', async (raw) => {
    resetWatchdog(activityTimeout);

    const message = JSON.parse(raw.toString());
    const data = parseEventData(message.data);

    switch (message.event) {
      case 'pusher:connection_established': {
        activityTimeout = data.activity_timeout ?? activityTimeout;
        console.log(`Connected with socket id ${data.socket_id}; subscribing to ${channelName}`);
        try {
          const auth = await authoriseChannel(data.socket_id, channelName);
          send('pusher:subscribe', { channel: channelName, ...auth });
        } catch (error) {
          console.error(error.message);
          socket.close();
        }
        return;
      }
      case 'pusher:ping':
        send('pusher:pong');
        return;
      case 'pusher:pong':
        return;
      case 'pusher_internal:subscription_succeeded':
        console.log(`Subscribed to ${message.channel}`);
        return;
      case 'pusher:error':
        console.error(`Server error${data?.code ? ` ${data.code}` : ''}: ${data?.message}`);
        return;
    }

    const handler = eventHandlers[message.event];
    if (handler) handler(data);
    else console.log(`Unhandled event ${message.event}:`, data);
  });

  socket.on('error', (error) => console.error('WebSocket error:', error.message));

  const closed = new Promise((resolve) => {
    socket.on('close', (code, reason) => {
      clearTimeout(watchdog);
      console.log(`WebSocket closed (${code}) ${reason.toString()}`);
      resolve();
    });
  });

  return { closed, close: () => socket.close(), service, channelName };
};

/**
 * Keeps a connection open to whichever service the platform names, reconnecting after a drop and
 * whenever the active service or the company channel changes.
 */
const establishWebSocketConnection = async () => {
  for (;;) {
    let connection;
    let serviceCheck;

    try {
      const details = await getConnectionDetails();
      connection = openConnection(details);

      serviceCheck = setInterval(async () => {
        try {
          const latest = await getConnectionDetails();
          const { service } = endpointFor(latest);
          const channelName = `private-${latest.channel_key}`;
          if (service !== connection.service || channelName !== connection.channelName) {
            console.log(`Connection details changed (now ${service}); reconnecting.`);
            connection.close();
          }
        } catch (error) {
          console.error('Could not re-check connection details:', error.message);
        }
      }, SERVICE_CHECK_INTERVAL_MS);

      await connection.closed;
    } catch (error) {
      console.error('Connection attempt failed:', error.message);
    } finally {
      clearInterval(serviceCheck);
    }

    console.log(`Reconnecting in ${RECONNECT_DELAY_MS / 1000}s...`);
    await new Promise((resolve) => setTimeout(resolve, RECONNECT_DELAY_MS));
  }
};

if (require.main === module) {
  establishWebSocketConnection();
}

exports.establishWebSocketConnection = establishWebSocketConnection;
exports.endpointFor = endpointFor;
