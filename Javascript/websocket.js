const { getTodMarketsEndpoint } = require('./API.js');
const Pusher = require('pusher-js');
require('dotenv').config();
require('./API.js');

const environmentURL = {
  label: "Environment URL",
  value: process.env.DOMAIN_URL.replace(/\/api\/?$/,'') // Remove trailing /api/ if present
};

const websocketDetails = {
  id: null,
  name: null,
  channel_key: null,
  channel_key_expiry: null,
  pusher_host: null,
  pusher_key: null,
  pusher_cluster: null
}

const setWebsocketDetails = (details) => {
  websocketDetails.id = details.id;
  websocketDetails.name = details.name;
  websocketDetails.channel_key = details.channel_key;
  websocketDetails.channel_key_expiry = details.channel_key_expiry;
  websocketDetails.pusher_host = details.pusher_host;
  websocketDetails.pusher_key = details.pusher_key;
  websocketDetails.pusher_cluster = details.pusher_cluster;
}

const getWebsocketDetails = async () => {
  await getTodMarketsEndpoint('/api/company')
    .then(response => {
      const res = JSON.parse(response);
      console.log('Websocket Details:', res.data);
      setWebsocketDetails(res.data);
      return res;
    })
    .catch(error => {
      console.error('Error fetching websocket details:', error);
    });
}

const channels = ref({
  "private-company": {
    name: () => `private-${websocketDetails.channel_key}`,
    instance: null,
    events: {
      "App\\Events\\AssetPriceChangeEventCompany": (e) => queueRowUpdate(e.data),
      "App\\Events\\OrderUpdated": (e) => queueRowUpdate(e.data),
      "App\\Events\\OrderFilled": (e) => queueRowUpdate(e.data),
      "App\\Events\\OrderCreated": (e) => queueRowUpdate(e.data),
    }
  }
});

const establishWebSocketConnection = async () => {
  await getWebsocketDetails();
  Pusher.logToConsole = true;
  const pusher = new Pusher(websocketDetails.pusher_key, {
    cluster: websocketDetails.pusher_cluster,
    wsHost: websocketDetails.pusher_host,
    activityTimeout: 30000,
    pongTimeout: 10000,
    wsPort: 80,
    forceTLS: false,
    authEndpoint: `${environmentURL.value}/broadcasting/auth`,
    auth: {
      headers: {
        'Authorization': `Bearer ${process.env.API_KEY}`
      }
    }
  });

  const channel = pusher.subscribe(websocketDetails.channel_key);
  channel.bind('update', function (data) {
    console.log('Received update:', data);
  }); 

  
  
}


if (require.main === module) {
    establishWebSocketConnection();
}