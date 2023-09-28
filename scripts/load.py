import asyncio
import aiohttp
import time
import os

# Define the URL of your website
url = "https://ai.featurebase.com"

# Define the number of concurrent requests to send
num_requests = 1000  # Adjust this to your testing needs

# Define the batch size
batch_size = 100

# Define the output file path
output_file = "latency_data.txt"
if os.path.exists(output_file):
    os.remove(output_file)

# Initialize max_latency with a small value (global variable)
max_latency = 0

# Lock for thread-safe access to max_latency
max_latency_lock = asyncio.Lock()

# Define a function to send an HTTP request asynchronously
async def send_request(session, request_number):
    global max_latency
    start_time = time.time()
    try:
        async with session.get(url) as response:
            response_text = await response.text()
            latency = time.time() - start_time
            status_code = response.status
            # Write latency data to the output file
            with open(output_file, "a") as file:
                file.write(f"Request {request_number}: Status code: {status_code}, Latency: {latency:.2f}s\n")
            # Update max_latency if a new maximum is found
            async with max_latency_lock:
                if latency > max_latency:
                    max_latency = latency
                    print(f"New Max Latency: {max_latency:.2f}s")
    except Exception as e:
        print(f"Request {request_number}: An error occurred: {str(e)}")

# Create an asynchronous event loop
async def main():
    async with aiohttp.ClientSession() as session:
        for batch_start in range(1, num_requests + 1, batch_size):
            batch_end = min(batch_start + batch_size, num_requests + 1)
            tasks = [send_request(session, i) for i in range(batch_start, batch_end)]
            await asyncio.gather(*tasks)
            if batch_end < num_requests + 1:
                print(f"Batch {batch_start}-{batch_end - 1} completed. Waiting...")
                await asyncio.sleep(5)  # Wait for 5 seconds before starting the next batch

if __name__ == "__main__":
    # Create or truncate the output file
    with open(output_file, "w") as file:
        file.write("")  # Clear the file

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

    # Print the maximum latency at the end
    print(f"Maximum Latency: {max_latency:.2f}s")

