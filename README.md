# SlothAI: A Model Pipeline Manager
SlothAI provides a simple and ansycronous methodology to implement document-based pipelines (chains) for various machine learning models. It is designed to be fast as hell.

<img src="https://github.com/FeatureBaseDB/SlothAI/blob/SlothAI/SlothAI/static/sloth.png?raw=true" width="240"/>

SlothAI is implemented in Python to run on AppEngine containers, and takes advantage of Cloud Task queues. SlothAI uses queues to asynchronously run inferencing on documents.

Machine learning box deployment is managed using [Laminoid](https://github.com/FeatureBaseDB/Laminoid).

## But, Why?
SlothAI is similar to LangChain, AutoChain, Auto-GPT, Ray and other machine learning frameworks that provide software opinionated model chains and model method management. Unlike these other solutions, SlothAI implements asynchronous inferencing while making it easy to edit templates and manage pipeline flows.

SlothAI's strategy for simplicity and scale is based on opinionated storage and compute layers. SlothAI requires using a SQL engine that can run both binary set operations and vector similarity running on containers using task queues.

## Pipeline Strategy
SlothAI creates *ingest pipelines* which contain *models*. Models run in sequence during ingestion. Their output is sent to a database table layer, which is currently FeatureBase. 

**NOTE:** The opinionated reason for using FeatureBase is due to its ability to process SQL to a) retrieve normal "tabular" data, b) run fast set operations (feature sets) using FB's binary tree storage layer, and c) run vector comparisons using FB's tuple storage layer. Subsequent updates to this repo will implement other storage layers, such as PostgreSQL with pgvector support and binary tree operations.

SlothAI also creates instances of *query pipelines*, which connect to a table and then batch resulting document data into a series of *ingest pipelines*. This combination of pipeline types allows for a wide variety of use cases.

**NOTE:** SlothAI uses dynamic templates which are stored on Github for version control. It also uses dynamic AI methods stored on Github, or ones synthesized by the LLM, to process the templates. A *schemer* model is used to update the templates from the schema detected in the POST payload.

### Sample Ingestion Graph
The following graph outlines an *ingestion pipeline* for new data that extracts keyterms, embeds the text and keyterms together, then forms a question about the text and keyterms using GPT-3.5-turbo:

<img src="https://raw.githubusercontent.com/FeatureBaseDB/SlothAI/SlothAI/SlothAI/static/pipeline_graph.png" width="360"/>

**NOTE:** An alternate strategy would be to form the questions from a given text fragment from a larger document by first storing the vectors and keyterms in FB, then running a query pipeline on the resulting dataset to allow for similarity search across all ingested documents, instead of just the text fragment and keyterms.

### Sample Query Graph
The following graph outlines a *query pipeline* for processing documents stored with keyterms, embeddings and questions. The output is an "answer" for the question posed, which is then stored in a new table:

<img src="https://raw.githubusercontent.com/FeatureBaseDB/SlothAI/SlothAI/SlothAI/static/query_graph.png" width="360"/>

In the above graph, the *slothy-answers* pipeline represents a series of *models* run on the batch requests, as seen above in the *ingest pipeline*.

## Sample Ingestion and Results
A sample ingestion pipeline use with instructor-xl embedding model & gpt-3.5-turbo to extract keyterms:

```
curl -X POST \
-H "Content-Type: application/json" \
-d '{"text":["There was a knock at the door, then silence."]}' \
"https://ai.featurebase.com/tables/L5IaljmIaox2H8r5U/ingest?token=9V1swMnuv0yonoywKqwtQ5_gD9"

# results can be returned with JSON or queried with SQL:
fbsql> SELECT _id, keyterms, text, embedding FROM test;

+---------+------------+-------------------+------------+
|   _id   |  keyterms  |       text        |  embedding |
+---------+------------+-------------------+------------+
| Oqhff1  |['knock','do| There was a knock | [0.02333,0.|
+---------+------------+-------------------+------------+
```

The instructor embedding model returns and stores a dense vector with a size of 768 elements:

```
-0.05440837,-0.016896732,-0.04767465,0.0016255669,0.0348847,0.0144764315,-0.0159672,-0.002682281,-0.04491195,0.025720688,0.044070743, etc.
```

This can be used to do similarity searches with SQL:
```
fbsql> select questions, text, cosine_distance(select embedding from demo where _id=2, embedding) as distance from demo order by distance desc;

To CSV:
questions,text,distance
What kind of watch is mentioned in the document?,Mechanical Watch,0.26853132
What happened after there was a knock at the door?,"There was a knock at the door, then silence.",0.25531703
Who has died?,Stephen Hawking has died,0.24436438
What is the content of the document?,GPT-4,0.24306345
What is the document reflecting on?,"Reflecting on one very, very strange year at Uber",0.23889714
Who has died?,Bram Moolenaar has died,0.2298429
Who has passed away?,Steve Jobs has passed away.,0.22849554
What is the title of the message?,A Message to Our Customers,0.20595884
What did Replit do to the user's open-source project?,Replit used legal threats to kill my open-source project,0.17009544
What was the outcome of the fair use case involving Google copying the Java SE API?,Google’s copying of the Java SE API was fair use [pdf],0.16320163
What organization issued a DMCA takedown to YouTube-dl?,YouTube-dl has received a DMCA takedown from RIAA,0
```

## Development Notes
* Embeddings, keyterm extraction, and question forming models are supported.
* Creation of ingestion pipelines is supported.
* Versioning for templates and model methods, query pipeline creation, and vector balancing are under development.
* Support for new model deployment occurs in the Laminoid project.
* Storage layer for PostgreSQL/pgvector is in planning.
* Alternate auth methods are being considered.

## Authentication
Authentication is currently limited to FeatureBase tokens ONLY. You must have a [FeatureBase cloud](https://cloud.featurebase.com/) account to use the application.

Security to the Laminoid controller is done through box tokens assigned to network tags in Google Compute. This secures the deployment somewhat, but could be better.

## Configuration
Create a `config.py` configuration file in the root directory. Use `config.py.example` to populate.

Keys, tokens and IPs are created as needed.

### Dependencies
Install conda and activate a new environment:

```
conda create -n slothai python=3.9
conda activate slothai
```

Install the requirements:

```
pip3 install -r requirements
```

## Install

To deploy to your own AppEngine:

```
./scripts/deploy.sh --production
```

Deploy the cron.yaml after updating the key (use the `cron.yaml.example` file):

```
gcloud app deploy cron.yaml
```

Create an AppEngine task queue (from the name in `config.py`):

```
gcloud tasks queues create sloth-spittle --location=us-central1 
```

To deploy for local development:

```
./scripts/dev.sh
```

## Testing

To run tests run the following from the root directory:

```
pytest
```

To get test coverage run:
```
pytest --cov=SlothAI --cov-report=html
```

## Use
Login to the system using your custom domain name, or the *appspot* URL, which you can find in the Google Cloud console.

For local development, use the following URL:

```
http://localhost:8080
```

### Login
To login to the system, use your FeatureBase Cloud [database ID](https://cloud.featurebase.com/databases) and [API key](https://cloud.featurebase.com/configuration/api-keys) (token).
