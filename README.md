# SlothAI: A Model Pipeline Manager
SlothAI provides a simple and ansycronous methodology to implement document-based pipelines (chains) for various models. It is designed to be fast as hell.

<img src="https://github.com/FeatureBaseDB/SlothAI/blob/SlothAI/static/sloth.png?raw=true" width="240"/>

SlothAI is implemented in Python to run on AppEngine containers, and takes advantage of Cloud Task queues. SlothAI uses queues to asyncronously run inferencing on documents.

Machine learning box deployment is managed using [Laminoid](https://github.com/FeatureBaseDB/Laminoid).

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
./deploy.sh
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
./dev.sh
```

## Use
Login to the system using your custom domain name, or the *appspot* URL, which you can find in the Google Cloud console.

For local development, use the following URL:

```
http://localhost:8080
```

### Login
To login to the system, use your FeatureBase Cloud [database ID](https://cloud.featurebase.com/databases) and [API key](https://cloud.featurebase.com/configuration/api-keys) (token).
