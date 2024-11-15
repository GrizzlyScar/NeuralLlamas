# -*- coding: utf-8 -*-
"""
Estimate Concentration from Band Powers with Real-Time Plotting (Display Value)

This script acquires EEG data, computes the band powers for delta, theta,
alpha, beta, and gamma waves, calculates a concentration value based on the Alpha/Beta ratio,
and plots each band power along with the concentration value in separate subplots in real-time.

Adapted from https://github.com/NeuroTechX/bci-workshop
"""

import numpy as np
import matplotlib.pyplot as plt
from pylsl import StreamInlet, resolve_byprop
import utils
import time


from websocket_server import WebsocketServer
import threading
import json

# Handy little enum to make code more readable
class Band:
    Delta = 0
    Theta = 1
    Alpha = 2
    Beta = 3
    Gamma = 4

""" EXPERIMENTAL PARAMETERS """
# Modify these to change aspects of the signal processing

# Length of the EEG data buffer (in seconds)
BUFFER_LENGTH = 5

# Length of the epochs used to compute the FFT (in seconds)
EPOCH_LENGTH = 1

# Amount of overlap between two consecutive epochs (in seconds)
OVERLAP_LENGTH = 0.8

# Amount to 'shift' the start of each next consecutive epoch
SHIFT_LENGTH = EPOCH_LENGTH - OVERLAP_LENGTH

# Index of the channel(s) (electrodes) to be used
INDEX_CHANNEL = [0]



# WebSocket server settings
HOST = 'localhost'
PORT = 8765

# List to keep track of connected clients
clients = []

def new_client(client, server):
    print(f"New client connected: {client['id']}")
    clients.append(client)

def client_left(client, server):
    print(f"Client disconnected: {client['id']}")
    clients.remove(client)

def send_eeg_data(data):
    # Convert the data dictionary to JSON string
    message = json.dumps(data)
    # Send the message to all connected clients
    server.send_message_to_all(message)

def run_websocket_server():
    global server
    server = WebsocketServer(host=HOST, port=PORT)
    server.set_fn_new_client(new_client)
    server.set_fn_client_left(client_left)
    print(f"WebSocket server started on ws://{HOST}:{PORT}")
    server.run_forever()

if __name__ == "__main__":

    # Start WebSocket server in a separate thread
    ws_thread = threading.Thread(target=run_websocket_server)
    ws_thread.daemon = True
    ws_thread.start()

    """ 1. CONNECT TO EEG STREAM """

    # Search for active LSL streams
    print('Looking for an EEG stream...')
    streams = resolve_byprop('type', 'EEG', timeout=2)
    if len(streams) == 0:
        raise RuntimeError("Can't find EEG stream.")

    # Set active EEG stream to inlet and apply time correction
    print("Start acquiring data")
    inlet = StreamInlet(streams[0], max_chunklen=12)
    eeg_time_correction = inlet.time_correction()

    # Get the stream info and description
    info = inlet.info()
    description = info.desc()

    # Get the sampling frequency
    fs = int(info.nominal_srate())

    """ 2. INITIALIZE BUFFERS """

    # Initialize raw EEG data buffer
    eeg_buffer = np.zeros((int(fs * BUFFER_LENGTH), 1))
    filter_state = None  # for use with the notch filter

    # Compute the number of epochs in "buffer_length"
    n_win_test = int(np.floor((BUFFER_LENGTH - EPOCH_LENGTH) /
                              SHIFT_LENGTH + 1))

    # Initialize the band power buffer (for plotting)
    band_buffer = np.zeros((n_win_test, 5))

    """ 3. SET UP REAL-TIME PLOT """

    # Initialize lists to store time, band powers, and concentration value
    times = []
    delta_powers = []
    theta_powers = []
    alpha_powers = []
    beta_powers = []
    gamma_powers = []
    concentration_values = []

    # Initialize the plot
    plt.ion()
    fig, axs = plt.subplots(6, 1, figsize=(10, 14), sharex=True)
    t0 = time.time()

    print('Press Ctrl-C in the console to break the while loop.')

    try:
        while True:

            """ 3.1 ACQUIRE DATA """
            eeg_data, timestamp = inlet.pull_chunk(
                timeout=1, max_samples=int(SHIFT_LENGTH * fs))

            # Only keep the channel we're interested in
            ch_data = np.array(eeg_data)[:, INDEX_CHANNEL]

            # Update EEG buffer with the new data
            eeg_buffer, filter_state = utils.update_buffer(
                eeg_buffer, ch_data, notch=True,
                filter_state=filter_state)

            """ 3.2 COMPUTE BAND POWERS """
            # Get newest samples from the buffer
            data_epoch = utils.get_last_data(eeg_buffer,
                                             EPOCH_LENGTH * fs)

            # Compute band powers
            band_powers = utils.compute_band_powers(data_epoch, fs)
            band_buffer, _ = utils.update_buffer(band_buffer,
                                                 np.asarray([band_powers]))
            # Compute the average band powers for all epochs in buffer
            smooth_band_powers = np.mean(band_buffer, axis=0)

            print("---------------------------------------------------------------------")

            print('Delta: ', band_powers[Band.Delta], ' Theta: ', band_powers[Band.Theta],
                  ' Alpha: ', band_powers[Band.Alpha], ' Beta: ', band_powers[Band.Beta],
                  ' Gamma: ', band_powers[Band.Gamma])

            """ 3.3 COMPUTE NEUROFEEDBACK METRICS """
            # These metrics could also be used to drive brain-computer interfaces

            # Alpha Protocol:
            # Simple readout of alpha power, divided by delta waves in order to rule out noise
            alpha_metric = smooth_band_powers[Band.Alpha] / \
                smooth_band_powers[Band.Delta]
            print('Alpha Relaxation: ', alpha_metric)

            # Beta Protocol:
            # Beta waves have been used as a measure of mental activity and concentration
            # This beta over theta ratio is commonly used as neurofeedback for ADHD
            beta_metric = smooth_band_powers[Band.Beta] / \
                smooth_band_powers[Band.Theta]
            print('Beta Concentration: ', beta_metric)

            # Alpha/Theta Protocol:
            # This is another popular neurofeedback metric for stress reduction
            # Higher theta over alpha is supposedly associated with reduced anxiety
            theta_metric = smooth_band_powers[Band.Theta] / \
                smooth_band_powers[Band.Alpha]
            print('Theta Relaxation: ', theta_metric)

            """ 3.3 COMPUTE CONCENTRATION VALUE """
            # Calculate concentration value
            # concentration_value = smooth_band_powers[Band.Alpha] / \
            #     smooth_band_powers[Band.Beta]
            # print('Concentration Value (Beta/Theta): ', concentration_value)

            # concentration_value = beta_metric



            #Calculate concentration value
            concentration_value = smooth_band_powers[Band.Alpha] / \
                smooth_band_powers[Band.Beta]
            print('Concentration Value (Alpha/Beta): ', concentration_value)


            """ 3.4 SEND DATA VIA WEBSOCKET """
            eeg_data_dict = {
                "alpha": smooth_band_powers[Band.Alpha],
                "beta": band_powers[Band.Theta],
                "theta": band_powers[Band.Theta],
                "delta":band_powers[Band.Delta],
                "gamma":band_powers[Band.Gamma],
                "concentration": concentration_value
            }
            send_eeg_data(eeg_data_dict)

            """ 3.4 UPDATE REAL-TIME PLOTS """
            current_time = time.time() - t0

            times.append(current_time)
            delta_powers.append(band_powers[Band.Delta])
            theta_powers.append(band_powers[Band.Theta])
            alpha_powers.append(band_powers[Band.Alpha])
            beta_powers.append(band_powers[Band.Beta])
            gamma_powers.append(band_powers[Band.Gamma])
            concentration_values.append(concentration_value)

            # Limit the x-axis to show only the last 30 seconds
            time_window = 30
            if current_time > time_window:
                xmin = current_time - time_window
                idx_min = np.searchsorted(times, xmin)
            else:
                xmin = 0
                idx_min = 0
            xmax = current_time

            # Clear each axis and plot the updated data
            axs[0].cla()
            axs[0].plot(times[idx_min:], delta_powers[idx_min:], label='Delta', color='b')
            axs[0].set_ylabel('Delta Power')
            axs[0].set_xlim([xmin, xmax])
            axs[0].legend(loc='upper right')
            axs[0].set_title('Delta Band Power')

            # Add text displaying the current delta value
            current_delta = delta_powers[-1]
            axs[0].text(0.05, 0.95, f'Current Value: {current_delta:.2f}',
                        transform=axs[0].transAxes, fontsize=12, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            axs[1].cla()
            axs[1].plot(times[idx_min:], theta_powers[idx_min:], label='Theta', color='g')
            axs[1].set_ylabel('Theta Power')
            axs[1].set_xlim([xmin, xmax])
            axs[1].legend(loc='upper right')
            axs[1].set_title('Theta Band Power')

            # Add text displaying the current theta value
            current_theta = theta_powers[-1]
            axs[1].text(0.05, 0.95, f'Current Value: {current_theta:.2f}',
                        transform=axs[1].transAxes, fontsize=12, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            axs[2].cla()
            axs[2].plot(times[idx_min:], alpha_powers[idx_min:], label='Alpha', color='r')
            axs[2].set_ylabel('Alpha Power')
            axs[2].set_xlim([xmin, xmax])
            axs[2].legend(loc='upper right')
            axs[2].set_title('Alpha Band Power')

            # Add text displaying the current alpha value
            current_alpha = alpha_powers[-1]
            axs[2].text(0.05, 0.95, f'Current Value: {current_alpha:.2f}',
                        transform=axs[2].transAxes, fontsize=12, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            axs[3].cla()
            axs[3].plot(times[idx_min:], beta_powers[idx_min:], label='Beta', color='m')
            axs[3].set_ylabel('Beta Power')
            axs[3].set_xlim([xmin, xmax])
            axs[3].legend(loc='upper right')
            axs[3].set_title('Beta Band Power')

            # Add text displaying the current beta value
            current_beta = beta_powers[-1]
            axs[3].text(0.05, 0.95, f'Current Value: {current_beta:.2f}',
                        transform=axs[3].transAxes, fontsize=12, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            # Plot gamma band power
            axs[4].cla()
            axs[4].plot(times[idx_min:], gamma_powers[idx_min:], label='Gamma', color='c')
            axs[4].set_ylabel('Gamma Power')
            axs[4].set_xlim([xmin, xmax])
            axs[4].legend(loc='upper right')
            axs[4].set_title('Gamma Band Power')

            # Add text displaying the current gamma value
            current_gamma = gamma_powers[-1]
            axs[4].text(0.05, 0.95, f'Current Value: {current_gamma:.2f}',
                        transform=axs[4].transAxes, fontsize=12, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            # Plot concentration value
            axs[5].cla()
            axs[5].plot(times[idx_min:], concentration_values[idx_min:], label='Concentration', color='k')
            axs[5].set_ylabel('Concentration')
            axs[5].set_xlim([xmin, xmax])
            axs[5].legend(loc='upper right')
            axs[5].set_xlabel('Time (s)')
            axs[5].set_title('Concentration (Alpha/Beta Ratio)')

            # Add text displaying the current concentration value
            current_concentration = concentration_values[-1]
            axs[5].text(0.05, 0.95, f'Current Value: {current_concentration:.2f}',
                        transform=axs[5].transAxes, fontsize=12, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            plt.tight_layout()
            plt.pause(0.01)

            """ 3.5 OPTIONAL: APPLY SMOOTHING OR NORMALIZATION """
            # If desired, you can apply smoothing to the concentration value
            # For example, using a moving average
            # window_size = 5
            # if len(concentration_values) >= window_size:
            #     smoothed_concentration = np.convolve(concentration_values, np.ones(window_size)/window_size, mode='valid')
            #     # Update the plot accordingly
            # print('Smoothed Concentration: ', smoothed_concentration)

        # The above code continues in the loop

    except KeyboardInterrupt:
        print('Closing!')

    finally:
        plt.ioff()
        plt.show()
