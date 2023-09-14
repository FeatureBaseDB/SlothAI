import matplotlib.pyplot as plt

# Initialize empty lists to store status codes and latencies
status_codes = []
latency_data = []

# Read data from the file
with open('latency_data.txt', 'r') as file:
    for line in file:
        if "Latency" in line:
            parts = line.split()
            latency = float(parts[-1][:-1])  # Remove 's' from the latency value
            latency_data.append(latency)

# Create a list of indices for the data points
indices = list(range(1, len(latency_data) + 1))

print(indices)
# Create a line plot for latency data
plt.figure(figsize=(10, 6))
plt.plot(indices, latency_data, marker='o', linestyle='-', color='b')

# Set plot labels and title
plt.xlabel('Request Number')
plt.ylabel('Latency (s)')
plt.title('Latency Plot')

# Show the plot
plt.grid(True)
plt.tight_layout()
plt.show()

