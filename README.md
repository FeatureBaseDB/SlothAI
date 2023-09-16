# SlothAI: An ML Chain Manager
SlothAI provides a simple UI and pipelines various models. Machine learning box deployment is managed using [Laminoid](https://github.com/FeatureBaseDB/Laminoid).

## Vector Managment
SlothAI implements [SlothANN](https://github.com/FeatureBaseDB/SlothAI/blob/SlothAI/SlothANN.md), a new type of approximate nearest neighbor (ANN) strategy using semantic graphs. SlothANN allows flexible and balanced vector storage, increasing the speed of retrevial no matter the ANN implmentation in the vector store.

## Authentication
Authentication is currently limited to FeatureBase tokens ONLY. You must have a [FeatureBase cloud](https://cloud.featurebase.com/) account to use the application.

Authentication will be extended to other methods soon, as well as other storage layers, such as PostgreSQL.

## Configuration
Create a `config.py` configuration file in the root directory. Instructions will follow to populate these settings.

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

### Authentication
To login to the system, use your FeatureBase Cloud [database ID](https://cloud.featurebase.com/databases) and [API key](https://cloud.featurebase.com/configuration/api-keys) (token).
