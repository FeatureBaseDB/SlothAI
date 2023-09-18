import asyncio
import random
import string
import aiohttp
from datetime import datetime

# Function to generate random text with words of 4-12 characters
import nltk

token = input("enter your ai.featurebase.com token: ")
tid = input("enter the tid: ")

# Download the list of common English words if you haven't already
nltk.download('words')

# Get a list of common English words
common_words = nltk.corpus.words.words()

# Function to generate a random sentence
def generate_random_sentence(word_count):
    sentence = " ".join(random.choice(common_words) for _ in range(word_count))
    return sentence


# Function to send a batch of records asynchronously
async def send_batch(url, records):
    headers = {"Content-Type": "application/json"}
    payload = {"text": records}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                print(f"Batch sent successfully.")
            else:
                print(f"Failed to send batch with status code: {response.status}")
                print(response.json)

async def main():
    # Record the start time
    start_time = datetime.now()
    print(f"Script started at: {start_time}")

    # Initialize a list to store records
    records = []

    # Create a list to store asyncio tasks for sending batches
    tasks = []

    # Loop to generate and send batches of 10 records
    for i in range(1, 51):
        random_text = generate_random_sentence(10)
        records.append(random_text)

        if i % 5 == 0:
            # Send a batch of 10 records asynchronously
            url = f"https://ai.featurebase.com/tables/{tid}/ingest?token={token}"
            url = f"http://localhost:8080/tables/{tid}/ingest?token={token}"
            print(records)
            tasks.append(send_batch(url, records))

            # Reset the records list for the next batch
            records = []

    # send the last batch
    tasks.append(send_batch(url, records))

    # Execute all tasks concurrently and wait for them to finish
    await asyncio.gather(*tasks)

    # Record the end time
    end_time = datetime.now()
    print(f"Script ended at: {end_time}")
    print(f"Total execution time: {end_time - start_time}")

if __name__ == "__main__":
    asyncio.run(main())

