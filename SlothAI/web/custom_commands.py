from flask import Blueprint, render_template
from flask import current_app as app
from faker import Faker

import nltk
from nltk.data import find
nltk.download('punkt')

# Load the Punkt tokenizer
tokenizer = nltk.data.load(find('tokenizers/punkt/english.pickle'))

custom_commands = Blueprint('custom_commands', __name__)

@custom_commands.app_template_global()
def reverse_word(word):
    reversed_word = word[::-1]
    return reversed_word

@custom_commands.app_template_global()
def random_word():
    fake = Faker()
    return fake.word()


@custom_commands.app_template_global()
def random_sentence():
    fake = Faker()
    return fake.sentence()


@custom_commands.app_template_global()
def process_and_segment_texts_with_overlap(texts, filename, overlap=0):
    segmented_texts = []
    page_numbers = []
    chunk_numbers = []
    filenames = []

    current_chunk_number = 1
    current_page_number = 1
    current_segment = ""

    for text in texts:
        # Initialize an empty list to store text segments for this text
        segments = []

        # Loop over the tokenized text
        for entry in tokenizer.tokenize(text):
            # Remove extra whitespace and newline characters
            entry = entry.strip().replace("\n"," ").replace("\r"," ").replace("\t"," ").replace('"','``').replace("'","`").replace("\\"," ")

            # Check if adding this entry to the current segment will exceed 512 characters
            if len(current_segment) + len(entry) > 512:
                # Append the current segment to the list
                segments.append(current_segment)
                current_segment = ""

            # Add the entry to the current segment
            current_segment += " " + entry

        # Append the last segment to the list if it's not empty
        if current_segment:
            segments.append(current_segment)

        # Combine overlapping segments based on the specified overlap parameter
        if overlap > 0:
            overlapped_segments = []
            for i in range(len(segments)):
                segment = segments[i]
                if i > 0:
                    # Combine with the last segment, considering the overlap
                    combined_segment = segments[i - 1][-overlap:] + segment
                    overlapped_segments.append(combined_segment)
                else:
                    overlapped_segments.append(segment)

            segments = overlapped_segments

        # Add the segmented text for this input to the final list
        segmented_texts.extend(segments)

        # Add page numbers, chunk numbers, and filenames
        page_numbers.extend([current_page_number] * len(segments))
        chunk_numbers.extend(list(range(current_chunk_number, current_chunk_number + len(segments))))
        filenames.extend([filename] * len(segments))

        # Update page and chunk numbers for the next text
        current_chunk_number += len(segments)
        current_page_number += 1

    return {
        "chunks": segmented_texts,
        "page_nums": page_numbers,
        "chunk_nums": chunk_numbers,
        "filenames": filenames
    }



