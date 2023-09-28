# SlothAI: A Model Pipeline Manager
SlothAI provides a simple and ansycronous methodology to implement document-based pipelines (chains) for various models. It is designed to be fast as hell.

<img src="https://github.com/FeatureBaseDB/SlothAI/SlothAI/blob/SlothAI/static/sloth.png?raw=true" width="240"/>

SlothAI is implemented in Python to run on AppEngine containers, and takes advantage of Cloud Task queues. SlothAI uses queues to asyncronously run inferencing on documents.

Machine learning box deployment is managed using [Laminoid](https://github.com/FeatureBaseDB/Laminoid).

## Sample Ingestion and Results
A sample pipeline using the instructor-xl embedding model & gpt-3.5-turbo to extract keyterms:

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

## Release Notes
* Authentication is supported with FeatureBase.
* Embeddings and keyterm extraction pipelines are supported.
* Local queue managment is supported.
* Templates and vector balancing are under development.
* Storage layer for PostgreSQL is under development.
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
