// Create a new WebSocket connection
const ws = new WebSocket('ws://localhost:8765');

// EEG data buffers
const alphaData = [];
const betaData = [];
const thetaData = [];
const deltaData = [];
const gammaData = [];
const concentrationData = [];
const labels = []; // Timestamps for the x-axis

// Create a real-time Chart.js line graph
const ctx = document.getElementById('eegChart').getContext('2d');
const eegChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: labels,
        datasets: [
            {
                label: 'Alpha',
                data: alphaData,
                borderColor: 'red',
                borderWidth: 2,
                fill: false,
            },
            {
                label: 'Beta',
                data: betaData,
                borderColor: 'blue',
                borderWidth: 2,
                fill: false,
            },
            {
                label: 'Theta',
                data: thetaData,
                borderColor: 'green',
                borderWidth: 2,
                fill: false,
            },
            {
                label: 'Delta',
                data: deltaData,
                borderColor: 'purple',
                borderWidth: 2,
                fill: false,
            },
            {
                label: 'Gamma',
                data: gammaData,
                borderColor: 'orange',
                borderWidth: 2,
                fill: false,
            },
            {
                label: 'Concentration',
                data: concentrationData,
                borderColor: 'black',
                borderWidth: 2,
                fill: false,
            },
        ],
    },
    options: {
        scales: {
            x: {
                title: {
                    display: true,
                    text: 'Time (s)',
                },
            },
            y: {
                title: {
                    display: true,
                    text: 'EEG Value',
                },
                beginAtZero: true,
            },
        },
    },
});

// WebSocket event handlers
ws.onopen = () => {
    console.log('Connected to WebSocket server.');
};

ws.onmessage = (event) => {
    try {
        const data = JSON.parse(event.data);
        const alpha = data.alpha;
        const beta = data.beta;
        const theta = data.theta;
        const delta = data.delta;
        const gamma = data.gamma;
        const concentration = data.concentration;

        // Add data to buffers
        const timestamp = new Date().toLocaleTimeString();
        labels.push(timestamp);
        alphaData.push(alpha);
        betaData.push(beta);
        thetaData.push(theta);
        deltaData.push(delta);
        gammaData.push(gamma);
        concentrationData.push(concentration);

        // Limit the number of data points to display (e.g., last 50 points)
        if (labels.length > 500000000000000) {
            labels.shift();
            alphaData.shift();
            betaData.shift();
            thetaData.shift();
            deltaData.shift();
            gammaData.shift();
            concentrationData.shift();
        }

        // Update the chart
        eegChart.update();

        console.log(`Alpha: ${alpha.toFixed(2)}, Beta: ${beta.toFixed(2)}, Theta: ${theta.toFixed(2)}, Delta: ${delta.toFixed(2)}, Gamma: ${gamma.toFixed(2)}, Concentration: ${concentration.toFixed(2)}`);
    } catch (error) {
        console.error('Error parsing message:', error);
    }
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('WebSocket connection closed.');
};
