// Determine the current hostname, port, and protocol
const hostname = window.location.hostname;
const port = window.location.port;

// Construct the WebSocket URL
const websocketURL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}${window.location.port ? `:${window.location.port}` : ''}${window.location.protocol === 'https:' ? '/homeinterface/websocket' : '/websocket'}`;

let websocket;

// Function to create WebSocket connection
function createWebSocket() {
    websocket = new WebSocket(websocketURL);

    websocket.onopen = function(event) {
        console.log("WebSocket connection established.");
        document.getElementById("websocketstatus").textContent = "Connected"; // Update status on the webpage
        sendStateCommand(); // Send state command on successful connection
    };

    websocket.onerror = function(error) {
        console.error("WebSocket error:", error);
        document.getElementById("websocketstatus").textContent = "Error"; // Update status on the webpage
    };

    // Handle messages from backend module <div id="light/magic/cabinetlights1state" class="status">unknown</div>
websocket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    const payload = JSON.parse(data.payload); // Parse the payload JSON string
    //console.log(payload); // Log the payload to the console for debugging
    const state = payload.state; // Extract the state from the payload
    const topic = data.topic; // Extract the topic from the message
    //console.log("got " + topic + " and " + state);

    // Transform slashes in topic into underscores for function name
    const functionName = topic.replace(/\//g, '_');
    //console.log("functionName:"+functionName)
    // Check if a function with the transformed name exists
    if (typeof window[functionName] === 'function') {
        // Call the function with the payload as an argument
        //console.log("calling:"+functionName+" with:"+payload)
        window[functionName](payload);
    } else {
        // Call the updateBulbState function with the topic and state
        //console.log("calling:updateBulbState with:"+topic+","+state)
        updateBulbState(topic, state);
    }
};

    websocket.onclose = function(event) {
        console.log("WebSocket connection closed. Reconnecting...");
        document.getElementById("websocketstatus").textContent = "Reconnecting"; // Update status on the webpage
        setTimeout(createWebSocket, 3000); // Retry connection after 3 seconds
    };
}

// Call function to create WebSocket connection initially
createWebSocket();

function isWebSocket() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        return true; // WebSocket connection is open
    } else {
        return false; // WebSocket connection is not open
    }
}

// Function to send command to backend module
/*function sendCommand(topic, command) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        const message = {
            topic: topic,
            payload: JSON.stringify({ command: command })
        };
        websocket.send(JSON.stringify(message));
    } else {
        console.error('WebSocket connection is not open');
    }
}*/

window.sendCommand = function(topic, command) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        const message = {
            topic: topic,
            payload: JSON.stringify({ command: command })
        };
        websocket.send(JSON.stringify(message));
    } else {
        console.error('WebSocket connection is not open');
    }
};


// Function to send state command on successful WebSocket connection or reconnection
function sendStateCommand() {
    // Find all elements with class "status"
    const statusElements = document.querySelectorAll(".status");

    // Iterate over each status element
    statusElements.forEach(function(element) {
        // Extract the ID of the element and remove "state" from the end
        const topic = element.id.replace(/state$/, "");

        // Send the state command for the extracted topic
        const message = {
            topic: topic,
            payload: JSON.stringify({ command: "state" })
        };
        websocket.send(JSON.stringify(message));
    });
}

// Function to update state on the webpage
function updateBulbState(topic, state) {
    topic = topic + "state";
    // Find the specific div with id "water/valve/2state"
    const divElement = document.getElementById(topic);
    
    // Check if divElement exists before proceeding
    if (!divElement) {
        //console.warn(`Element with id ${topic} not found.`);
        return; // Exit the function if divElement is not found
    }

    // Update status text
    divElement.textContent = state;

    // Find the child img element within the div
    const imgElement = divElement.nextElementSibling;

    // Check if imgElement is defined
    if (!imgElement) {
        //console.warn(`No next sibling image element found for ${topic}.`);
        return; // Exit the function if imgElement is not found
    }

    // Determine the image URL based on the state
    const imageUrl = state === '000000' || state === '000100' || state === '0000' || state === '0' ? 'bulboff.png' : 'bulbon.png';
    
    // Update the image source
    imgElement.src = imageUrl;
}

// Function to handle button clicks
document.body.addEventListener('click', function(event) {
    const target = event.target;
    if (target.matches('button')) {
        const buttonId = target.id;
        const lastSlashIndex = buttonId.lastIndexOf('/');
        const topic = buttonId.substring(0, lastSlashIndex);
        const command = buttonId.substring(lastSlashIndex + 1); // Get everything after the last slash
        sendCommand(topic, command);
    }
});

let resizeTimeout;
let lastWidth = window.innerWidth;
let lastHeight = window.innerHeight;

function handleResize() {
    clearTimeout(resizeTimeout);

    // Set a timeout to debounce the resize event
    resizeTimeout = setTimeout(() => {
        const newWidth = window.innerWidth;
        const newHeight = window.innerHeight;

        if (newWidth !== lastWidth) {
            // Call the function related to state command after the debounce timeout
            sendStateCommand();
        }

        // Update lastWidth and lastHeight for the next comparison
        lastWidth = newWidth;
        lastHeight = newHeight;
    }, 300); // Adjust the debounce delay as needed (e.g., 300ms)
}

window.addEventListener('resize', handleResize);


