# TOD Markets API Examples

This repository contains example code for interacting with the TOD Markets API. The examples demonstrate how to authenticate, retrieve market data, and place orders using various programming languages.

The examples are intended for educational purposes and should be adapted to fit your specific use cases and requirements.

## Getting Started

Visit the [TOD Markets API Documentation (Postman)](https://documenter.getpostman.com/view/36349395/2sA3XQi2Vb) to learn more about the available endpoints and how to use them.


## The Examples

The examples are organized into folders based on the programming language used. Each folder contains code snippets and instructions for setting up and running the examples.

You can make use of the provided `.env.example` file to configure your environment variables, such as your API key and domain URL.

We recommend testing with the staging environment before deploying to production. The staging domain URL is `https://staging.todmarkets.com.au/api/`.

## WebSocket Examples

TOD Markets publishes live updates through one of two services, both speaking the Pusher protocol (version 7):

- **Reverb**, TOD Markets' own WebSocket server. This is the primary service.
- **Pusher**, the hosted service TOD Markets used previously, kept as a fallback.

The platform can switch between them at any time, and neither service tells connected clients when it does. A client left on the inactive service stays connected but receives nothing. `GET /api/company` names the active service in `broadcast_driver`, so both examples follow the same flow:

1. Call `/api/company` to get the channel key and the connection details for both services.
2. Connect to the service named by `broadcast_driver`:
	- `reverb`: `wss://{reverb_host}:{reverb_port}/app/{reverb_key}` (`ws://` only when `reverb_use_tls` is false)
	- `pusher`, or the field is absent: `wss://ws-{pusher_cluster}.pusher.com/app/{pusher_key}`
3. Send an `Origin` header set to the platform address (your `DOMAIN_URL` without `/api`). Reverb can reject a handshake whose Origin it does not recognise, with `pusher:error` code 4009.
4. On `pusher:connection_established`, authorise `private-{channel_key}` by POSTing `socket_id` and `channel_name` to `/api/broadcasting/auth` with your Bearer token, then send `pusher:subscribe` with the returned `auth`.
5. Answer every `pusher:ping` with `pusher:pong`.
6. Re-read `/api/company` every few minutes and reconnect if `broadcast_driver` or `channel_key` has changed. Re-read it before every reconnection too.

Channel authorisation is always signed for the active service, so subscribing on the inactive one fails with "Invalid key in subscription auth data". Follow `broadcast_driver` rather than trying each service in turn.

Both examples connect over a plain WebSocket and implement the protocol directly so that they can set the `Origin` header, which `pusher-js` does not allow under Node.js. In a browser, `pusher-js` or Laravel Echo work unchanged: the browser sends `Origin` itself. Configure them with `wsHost`, `wsPort`, `wssPort` and `forceTLS` from the `reverb_*` fields when `broadcast_driver` is `reverb`.

### JavaScript WebSocket Example

File: [Javascript/websocket.js](Javascript/websocket.js)

**Setup**

1. Create a `.env` file with:
	- `API_KEY`
	- `DOMAIN_URL` (for example, `https://staging.todmarkets.com.au/api/`)
2. Install dependencies:
	- `npm install`

**Run**

- `node Javascript/websocket.js`

**Notes**

- The script uses the `ws` library and implements the Pusher protocol handshake described above.
- It reconnects after a drop, and whenever `/api/company` reports a different service or channel.
- Incoming events are routed to handlers for `AssetPriceChangeEventCompany`, `OrderCreated`, `OrderUpdated` and `OrderFilled`.

### Python WebSocket Example

File: [Python/websocket.py](Python/websocket.py)

**Setup**

1. Create a `.env` file with:
	- `API_KEY`
	- `DOMAIN_URL` (for example, `https://staging.todmarkets.com.au/api/`)
2. Install dependencies:
	- `python -m pip install --user websocket-client python-dotenv requests`

**Run**

- `python Python/websocket.py`

**Notes**

- The script uses the `websocket-client` library and implements the Pusher protocol handshake described above.
- It reconnects after a drop, and whenever `/api/company` reports a different service or channel.
- Incoming events are routed to handlers for `AssetPriceChangeEventCompany`, `OrderCreated`, `OrderUpdated` and `OrderFilled`.


## Contributing

Contributions are welcome! If you have an example you'd like to share or improvements to suggest, please open a pull request or issue in this repository.


