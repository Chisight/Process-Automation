// graphing functions:

function findMinMax(jsonData) {
    const fields = Object.keys(jsonData);
    const minMaxValues = {};

    // Initialize min and max values for each field
    fields.forEach(field => {
        minMaxValues[field] = {
            min: Infinity,
            max: -Infinity
        };
    });

    // Loop through each array in the JSON data
    fields.forEach(field => {
        const values = jsonData[field].map(value => value !== "null" ? parseFloat(value) : null); // Convert "null" to null
        values.forEach(value => {
            if (!isNaN(value) && value !== null) {
                minMaxValues[field].min = Math.min(minMaxValues[field].min, value);
                minMaxValues[field].max = Math.max(minMaxValues[field].max, value);
            }
        });
    });

    return minMaxValues;
}

//interval=ceil((ceil(max)-floor(min))/(divisions-1)) seems to be the generic formula.  
//first grid line is floor(min), last grid line is floor(min)+interval*(divisions-1). 
function adjustMinMax(min, max, divisions) {
    const minY=Math.floor(min); //for the moment ignoring that this may not center the graph perfectly
    const interval=Math.ceil((Math.ceil(max)-minY)/(divisions-1))
    const maxY=minY+interval*(divisions-1)
//console.log('min:', min);
//console.log('max:', max);
//console.log('divisions:', divisions);
//console.log('interval:', interval);
//console.log('minY:', minY);
//console.log('maxY:', maxY);
    return [ minY, maxY ];
}

// Function to convert local time string to Date object
function parseLocalTime(localTimeStr) {
    return new Date(localTimeStr);
}

// Create a map to store display elements
const displayElementsMap = new Map();

function setLegend(legend, field, color, displayValue = null) {
    // Create a unique key based on the container's id and the field
    const containerId = legend.parentNode.id; // Get the id of the parent container
    const uniqueKey = `${containerId}-${field}`; // Create a unique key

    // Check if an element with the same id (field) already exists in legend
    let legendItem = legend.querySelector(`#${field}`);
    
    if (!legendItem) {
        // If it doesn't exist, create a new one
        legendItem = document.createElement('div');
        legendItem.id = field; // Set the div id to the value of field
        legendItem.style.display = 'inline-flex'; // Display inline
        legendItem.style.alignItems = 'center';

        const colorBox = document.createElement('div');
        colorBox.style.width = '15px';
        colorBox.style.height = '15px'; // Make it square
        colorBox.style.backgroundColor = color;
        colorBox.style.marginLeft = '5px';
        colorBox.style.marginRight = '1px';
        legendItem.appendChild(colorBox);

        const legendText = document.createElement('span');
        legendText.textContent = `${field}`;
        legendItem.appendChild(legendText);

        legend.appendChild(legendItem);
    }

    if (displayValue !== null) {
        // Check if a display element for this unique key already exists
        let displayElement = displayElementsMap.get(uniqueKey);
        
        if (!displayElement) {
            // If it doesn't exist, create a new display element
            displayElement = document.createElement('div');
            displayElement.style.position = 'absolute';
            displayElement.style.display = 'none';
            displayElement.style.backgroundColor = 'black';
            displayElement.style.padding = '5px';
            displayElement.style.zIndex = '1000';

            document.body.appendChild(displayElement);
            // Store the display element in the map using the unique key
            displayElementsMap.set(uniqueKey, displayElement);
        }

        // Update the content of the display element
        if (typeof displayValue !== 'number' && displayValue.startsWith('http')) {
            const img = document.createElement('img');
            img.src = displayValue;
            displayElement.innerHTML = ''; // Clear previous content
            displayElement.appendChild(img);
        } else {
            displayElement.textContent = displayValue;
        }

        const showDisplayValue = (event) => {
            displayElement.style.display = 'block';

            // Positioning logic (same as before)
            const scrollX = window.scrollX || window.pageXOffset;
            const scrollY = window.scrollY || window.pageYOffset;
            let leftPosition = event.clientX + scrollX + 10;
            let topPosition = event.clientY + scrollY + 10;

            // Check if the element would go off-screen
            if (leftPosition + displayElement.offsetWidth > window.innerWidth + scrollX) {
                leftPosition = window.innerWidth + scrollX - displayElement.offsetWidth;
            }
            if (topPosition + displayElement.offsetHeight > window.innerHeight + scrollY) {
                topPosition = window.innerHeight + scrollY - displayElement.offsetHeight;
            }

            displayElement.style.left = `${leftPosition}px`;
            displayElement.style.top = `${topPosition}px`;
        };

        const hideDisplayValue = (event) => {
            if (!legendItem.contains(event.relatedTarget) && !displayElement.contains(event.relatedTarget)) {
                displayElement.style.display = 'none';
            }
        };

        // Add event listeners for showing and hiding the display value
        legendItem.addEventListener('mouseover', showDisplayValue);
        legendItem.addEventListener('mouseout', hideDisplayValue);
        displayElement.addEventListener('mouseout', hideDisplayValue);
        legendItem.addEventListener('touchstart', showDisplayValue);
        legendItem.addEventListener('touchend', hideDisplayValue);
    }
}


function plotLine(container, canvas, legend, data, field, color, minValue, maxValue, gridPosition, displayValue = null, skipGaps = false) {
    const ctx = canvas.getContext('2d');
    ctx.font = '10px Arial';

    const gridHeight = canvas.height - 30;
    const gridWidth = gridPosition.rightmost - gridPosition.leftmost;
    const HorizontalOffset = gridPosition.leftmost;
    const VerticalOffset = 10;

    const startTime = parseLocalTime(data.time[0]);
    const values = data[field] ? data[field].map(value => value !== "null" ? parseFloat(value) : null) : [];

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;

    let previousValidX = null;
    let previousValidY = null;
    let previousValidTime = null;

    data.time.forEach((time, index) => {
        const value = values[index];
        const currentTime = parseLocalTime(time);

        if (value !== null) {
            const x = ((currentTime - startTime) / (parseLocalTime(data.time[data.time.length - 1]) - startTime)) * gridWidth + HorizontalOffset;
            const y = (1 - (value - minValue) / (maxValue - minValue)) * gridHeight + VerticalOffset;

            if (previousValidX === null) {
                ctx.beginPath();
                ctx.moveTo(x, y);
            } else {
                // Check if y is falling to minimum or zero
                const minY = (1 - (Math.max(0, minValue) - minValue) / (maxValue - minValue)) * gridHeight + VerticalOffset;
                if (y >= minY && previousValidY < minY) {
                    ctx.lineTo(x, previousValidY);
                    ctx.lineTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            }

            previousValidX = x;
            previousValidY = y;
            previousValidTime = currentTime;
        } else if (skipGaps && previousValidX !== null) {
            // Stroke the current path when encountering a gap
            ctx.stroke();
            previousValidX = null;
            previousValidY = null;
        }
    });

    // Stroke the final path
    ctx.stroke();
    setLegend(legend, field, color, displayValue);
}


// Function to clear legend
function clearLegend(legend) {
    legend.innerHTML = ''; // Remove all child elements
}

// Function to draw grid and labels
function drawGrid(container, canvas, jsonData, leftmin, leftmax, rightmin, rightmax, count) {
    const ctx = canvas.getContext('2d');
    ctx.font = '10px Arial';

    const leftOffset = ctx.measureText(Math.max(Math.abs(leftmin), Math.abs(leftmax)).toString()).width;
    const rightOffset = rightmax !== 0 || rightmin !== 0 ? ctx.measureText(Math.max(Math.abs(rightmin), Math.abs(rightmax)).toString()).width : 0;

    canvas.width = container.clientWidth -5;
    canvas.height = 230;
    const gridHeight = canvas.height - 30;
    const gridWidth = canvas.width - leftOffset - rightOffset - 25;
    const HorizontalOffset = leftOffset + 10;
    const VerticalOffset = 10;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#606060';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(HorizontalOffset, VerticalOffset);
    ctx.lineTo(gridWidth + HorizontalOffset, VerticalOffset);
    ctx.lineTo(gridWidth + HorizontalOffset, gridHeight + VerticalOffset);
    ctx.lineTo(HorizontalOffset, gridHeight + VerticalOffset);
    ctx.lineTo(HorizontalOffset, VerticalOffset);
    ctx.stroke();

    const spacing = gridHeight / (count - 1);

    ctx.fillStyle = 'white';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i < count; i++) {
        const leftValue = leftmin + (leftmax - leftmin) * (1 - i / (count - 1));
        const rightValue = rightmin + (rightmax - rightmin) * (1 - i / (count - 1));
        ctx.fillText(Math.round(leftValue), HorizontalOffset - 5, VerticalOffset + i * spacing);
        if (rightmin != 0 || rightmax != 0) {
            ctx.fillText(Math.round(rightValue), gridWidth + HorizontalOffset + 15, VerticalOffset + i * spacing);
        }
        ctx.beginPath();
        ctx.moveTo(HorizontalOffset, VerticalOffset + i * spacing);
        ctx.lineTo(gridWidth + HorizontalOffset, VerticalOffset + i * spacing);
        ctx.stroke();
    }

    ctx.fillStyle = 'white';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const times = jsonData.time.map(time => new Date(time * 1000));
    const dataLength = times.length;
    const timeDifference = times[dataLength - 1] - times[0];

function drawLinesAndLabels(times, timeUnit) {
    const rawTimestamps = jsonData.time;

    if (times.length === 0) {
        return;
    }

    const startTime = times[0].getTime();
    const endTime = times[times.length - 1].getTime();
    const timeRange = endTime - startTime;

    console.log(`startTime: ${startTime} endTime: ${endTime} gridWidth: ${gridWidth} HorizontalOffset: ${HorizontalOffset}`);

    let unitValues = [];
    if (timeUnit === 'day') {
        const startDate = new Date(startTime);
        const endDate = new Date(endTime);
        // Ensure the end date includes the last day
        endDate.setDate(endDate.getDate() + 1);
        // swap if start time is greater than end time
        if (startTime > endTime) {
            const temp = startDate;
            startDate.setTime(endDate.getTime());
            endDate.setTime(temp.getTime());
        }

        let currentDate = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate(), 0, 0, 0, 0);
        while (currentDate.getTime() <= endDate.getTime()) {
            if (currentDate.getTime() >= Math.min(startTime, endTime) && currentDate.getTime() <= Math.max(startTime, endTime)) {
                unitValues.push({ time: currentDate.getTime(), label: `${currentDate.getMonth() + 1}/${currentDate.getDate()}` });
            }
            currentDate.setDate(currentDate.getDate() + 1);
        }
    } else if (timeUnit === 'hour') {
        const startDate = new Date(startTime);
        const endDate = new Date(endTime);
        // Ensure the end date includes the last hour
        endDate.setHours(endDate.getHours() + 1);
        // swap if start time is greater than end time
        if (startTime > endTime) {
            const temp = startDate;
            startDate.setTime(endDate.getTime());
            endDate.setTime(temp.getTime());
        }

        let currentHour = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate(), startDate.getHours(), 0, 0, 0);
        while (currentHour.getTime() <= endDate.getTime()) {
            if (currentHour.getTime() >= Math.min(startTime, endTime) && currentHour.getTime() <= Math.max(startTime, endTime)) {
                unitValues.push({ time: currentHour.getTime(), label: `${currentHour.getDate()}:${currentHour.getHours()}` });
            }
            currentHour.setHours(currentHour.getHours() + 1);
        }
    } else if (timeUnit === 'minute30') {
        const startDate = new Date(startTime);
        const endDate = new Date(endTime);
        // Ensure the end date includes the last minute30
        endDate.setMinutes(endDate.getMinutes() + 30);
        // swap if start time is greater than end time
        if (startTime > endTime) {
            const temp = startDate;
            startDate.setTime(endDate.getTime());
            endDate.setTime(temp.getTime());
        }

        let currentMinute = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate(), startDate.getHours(), startDate.getMinutes() - (startDate.getMinutes() % 30), 0, 0);
        while (currentMinute.getTime() <= endDate.getTime()) {
            if (currentMinute.getTime() >= Math.min(startTime, endTime) && currentMinute.getTime() <= Math.max(startTime, endTime)) {
                unitValues.push({ time: currentMinute.getTime(), label: `${currentMinute.getHours()}:${String(currentMinute.getMinutes()).padStart(2, '0')}` });
            }
            currentMinute.setMinutes(currentMinute.getMinutes() + 30);
        }
    } else if (timeUnit === 'minute10') {
        const startDate = new Date(startTime);
        const endDate = new Date(endTime);
        // Ensure the end date includes the last minute10
        endDate.setMinutes(endDate.getMinutes() + 10);
        // swap if start time is greater than end time
        if (startTime > endTime) {
            const temp = startDate;
            startDate.setTime(endDate.getTime());
            endDate.setTime(temp.getTime());
        }

        let currentMinute = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate(), startDate.getHours(), startDate.getMinutes() - (startDate.getMinutes() % 10), 0, 0);
        while (currentMinute.getTime() <= endDate.getTime()) {
            if (currentMinute.getTime() >= Math.min(startTime, endTime) && currentMinute.getTime() <= Math.max(startTime, endTime)) {
                unitValues.push({ time: currentMinute.getTime(), label: `${currentMinute.getHours()}:${String(currentMinute.getMinutes()).padStart(2, '0')}` });
            }
            currentMinute.setMinutes(currentMinute.getMinutes() + 10);
        }
    }

    // Draw vertical lines and labels for each filtered unit
    unitValues.forEach(unitData => {
        const x = ((unitData.time - startTime) / timeRange) * gridWidth + HorizontalOffset;

        ctx.beginPath();
        ctx.moveTo(x, VerticalOffset);
        ctx.lineTo(x, gridHeight + VerticalOffset);
        ctx.stroke();
        ctx.fillText(unitData.label, x, gridHeight + VerticalOffset + 10);
        console.log(`Timestamp: ${unitData.time}, Label: ${unitData.label}, X Offset: ${x}`);
    });
}

    if (timeDifference > 50 * 60 * 60 * 1000) {
        drawLinesAndLabels(times, 'day');
    } else if (timeDifference > 5 * 60 * 60 * 1000) {
        drawLinesAndLabels(times, 'hour');
    } else if (timeDifference > 60 * 60 * 1000) {
        drawLinesAndLabels(times, 'minute30');
    } else {
        drawLinesAndLabels(times, 'minute10');
    }

    let gridPosition = { leftmost: HorizontalOffset, rightmost: HorizontalOffset + gridWidth };
    if (times.length > 1) {
        gridPosition.leftmost = HorizontalOffset;
        gridPosition.rightmost = HorizontalOffset + gridWidth;
    }
    return gridPosition;
}

function openTab(evt, tabName) {
    // Get all elements with class="tab-content" and hide them
    let tabContent = document.getElementsByClassName("tab-content");
    for (let i = 0; i < tabContent.length; i++) {
        tabContent[i].style.display = "none";
        tabContent[i].classList.remove("active");
    }

    // Get all elements with class="tab-link" and remove the class "active"
    let tabLinks = document.getElementsByClassName("tab-link");
    for (let i = 0; i < tabLinks.length; i++) {
        tabLinks[i].classList.remove("active");
    }

    // Show the current tab, and add an "active" class to the button that opened the tab
    document.getElementById(tabName).style.display = "block";
    document.getElementById(tabName).classList.add("active");
    evt.currentTarget.classList.add("active");
    //resize the graphs
    sendStateCommand();
}

// Dial controls
const THROTTLE_WAIT_TIME = 100; 

function initDial(container, min, max, deadband, command) {
    const dialRadius = parseInt(container.getAttribute('data-radius'));
    const redDot = container.querySelector('.red-dot');
    const dialImage = container.querySelector('.dial'); // Get the dial image element

    if (!redDot || !dialImage) {
        console.error('Red dot or dial element not found within the container.');
        return;
    }

    // Set the size of the dial container based on the dial radius
    const containerSize = dialRadius * 2; // Full diameter
    container.style.width = `${containerSize}px`;
    container.style.height = `${containerSize}px`;

    // Create the throttled sendValueCommand function using the command string
    const sendValueCommand = throttle((value) => {
        sendCommand(command, value);
    }, THROTTLE_WAIT_TIME);

    let isDragging = false;
    let lastSentValue = null; 

    function setupEventListeners() {
        container.addEventListener('mousedown', handleMouseDown);
        container.addEventListener('mousemove', handleMouseMove);
        container.addEventListener('mouseup', handleMouseUp);
    }

    function cleanupEventListeners() {
        container.removeEventListener('mousedown', handleMouseDown);
        container.removeEventListener('mousemove', handleMouseMove);
        container.removeEventListener('mouseup', handleMouseUp);
    }

    function handleMouseDown(event) {
        isDragging = true;
        updateRotation(event);
        event.preventDefault();
    }

    function handleMouseMove(event) {
        if (isDragging) {
            updateRotation(event);
        }
    }

    function handleMouseUp() {
        isDragging = false;
    }

    function updateRotation(event) {
        const rect = container.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;

        const mouseX = event.clientX;
        const mouseY = event.clientY;

        const angle = Math.atan2(mouseY - centerY, mouseX - centerX);
        const normalizedAngle = (angle + Math.PI / 2 + 2 * Math.PI) % (2 * Math.PI);

        const adjustedMin = min - deadband;
        const adjustedMax = max + deadband;

        const normalized = normalizedAngle / (2 * Math.PI);
        let value = normalized * (adjustedMax - adjustedMin) + adjustedMin;

        const clampedValue = Math.max(min, Math.min(max, Math.round(value)));

        if (clampedValue !== lastSentValue) {
            sendValueCommand(clampedValue); // Call the throttled function
            lastSentValue = clampedValue;
        }
        updateRedDotPosition(clampedValue, min, max, container);
    }

    setupEventListeners();
    window.addEventListener('beforeunload', cleanupEventListeners);
}

function updateRedDotPosition(value, min, max, container) {
    const dialRadius = parseInt(container.getAttribute('data-radius'));
    const redDot = container.querySelector('.red-dot');
    const rect = container.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    // Calculate the angle based on the value
    const degrees = ((value - min) / (max - min)) * 360 - 90; // Adjust for starting position
    const radians = degrees * (Math.PI / 180);

    // Calculate the position of the red dot
    const dotX = centerX + (dialRadius - 10) * Math.cos(radians); // Red dot radius is 10 smaller
    const dotY = centerY + (dialRadius - 10) * Math.sin(radians); // Red dot radius is 10 smaller

    // Log the intermediate values
    //console.log(min, max, dialRadius, centerX, centerY, "value:", value, "degrees:", degrees, "radians:", radians, "dotX:", dotX, "dotY:", dotY);

    requestAnimationFrame(() => {
        redDot.style.left = `${dotX - rect.left}px`;
        redDot.style.top = `${dotY - rect.top}px`;
    });
}

function initLinearslider(container, min, max, command) {
    const sliderWidth = parseInt(container.getAttribute('data-width'));
    const handle = container.querySelector('.handle');
    const sliderImage = container.querySelector('.linear-slider');

    if (!handle || !sliderImage) {
        console.error('Handle or linear slider element not found within the container.');
        return;
    }

    container.style.width = `${sliderWidth}px`;
    container.style.height = `${sliderImage.offsetHeight}px`; // Match height to the image

    const sendValueCommand = throttle((value) => {
        sendCommand(command, value);
    }, THROTTLE_WAIT_TIME);

    let isDragging = false;
    let lastSentValue = null;

    function setupEventListeners() {
        handle.addEventListener('mousedown', handleMouseDown);
        sliderImage.addEventListener('mousedown', handleMouseDown);
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
    }

    function cleanupEventListeners() {
        handle.removeEventListener('mousedown', handleMouseDown);
        sliderImage.removeEventListener('mousedown', handleMouseDown);
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
    }

    function handleMouseDown(event) {
        isDragging = true;
        updatePosition(event, container, min, max, sendValueCommand);
        event.preventDefault();
    }

    function handleMouseMove(event) {
        if (isDragging) {
            updatePosition(event, container, min, max, sendValueCommand);
        }
    }

    function handleMouseUp() {
        isDragging = false;
    }

    function updatePosition(event, container, min, max, sendValueCommand) {
        const rect = container.getBoundingClientRect();
        const handleRect = handle.getBoundingClientRect();
        const mouseX = event.clientX;
        const handleWidth = handleRect.width;

        const usableWidth = rect.width - handleWidth;
        const deadSpace = usableWidth * 0.10; // 10% dead space on each end
        let position = mouseX - rect.left - handleWidth / 2;
        position = Math.max(deadSpace, Math.min(position, usableWidth - deadSpace));

        const normalized = (position - deadSpace) / (usableWidth - 2 * deadSpace); // Adjust normalization for dead space
        let value = normalized * (max - min) + min;

        const clampedValue = Math.max(min, Math.min(max, Math.round(value)));

        if (clampedValue !== lastSentValue) {
            sendValueCommand(clampedValue);
            lastSentValue = clampedValue;
        }

        requestAnimationFrame(() => {
            handle.style.left = `${position}px`;
        });
    }

    setupEventListeners();
    window.addEventListener('beforeunload', cleanupEventListeners);
}

function updateHandlePosition(value, min, max, container) {
console.log("updateHandlePosition: "+value)
    const sliderWidth = parseInt(container.getAttribute('data-width'));
    const handle = container.querySelector('.handle');
    const rect = container.getBoundingClientRect();
    const handleRect = handle.getBoundingClientRect();
    const handleWidth = handleRect.width;

    const usableWidth = sliderWidth - handleWidth;
    const deadSpace = usableWidth * 0.10; // 10% dead space on each end

    const normalized = (value - min) / (max - min);
    const position = normalized * (usableWidth - 2 * deadSpace) + deadSpace;

    requestAnimationFrame(() => {
        handle.style.left = `${position}px`;
    });
}


function throttle(func, limit) {
    let lastFunc;
    let lastRan;
    return function(...args) {
        const context = this;
        if (!lastRan) {
            func.apply(context, args);
            lastRan = Date.now();
       } else {
            clearTimeout(lastFunc);
            lastFunc = setTimeout(function() {
                if ((Date.now() - lastRan) >= limit) {
                    func.apply(context, args);
                    lastRan = Date.now();
                }
            }, limit - (Date.now() - lastRan));
        }
    };
}


