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

These examples demonstrate the private authenticated WebSocket handshake flow:

1. Call `/api/company` to retrieve WebSocket connection details (Pusher key, cluster, and channel key).
2. Establish a WebSocket connection and authenticate the private channel subscription.
3. Listen for updates on the private company channel.

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

- The script uses `Pusher` with the `authEndpoint` at `/broadcasting/auth` and includes the `Authorization: Bearer <API_KEY>` header.
- It subscribes to the private company channel and logs update events.

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

- The script uses the `websocket-client` library and implements the Pusher protocol handshake.
- It authenticates the private channel via `/broadcasting/auth` (with a fallback to `/api/broadcasting/auth` when needed).
- Incoming events are routed to handlers for `AssetPriceChangeEventCompany`, `OrderUpdated`, `OrderFilled`, and `OrderCreated`.


## Contributing

Contributions are welcome! If you have an example you'd like to share or improvements to suggest, please open a pull request or issue in this repository.


