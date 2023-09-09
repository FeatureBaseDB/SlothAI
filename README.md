# SlothAI: Model API Manager
SlothAI serves various models from a Google AppEngine project. Job deployment is managed using a Button box.

SlothAI implements [SlothANN](https://github.com/FeatureBaseDB/SlothAI/blob/SlothAI/SlothANN.md), a new type of approximate nearest neighbor indexing and search strategy for efficiently handling large volumes of high-dimensional data in data analysis and information retrieval tasks.

Authentication is currently limited to FeatureBase tokens ONLY. You must have a FeatureBase cloud account to use the application.

## Configuration
Create a `config.py` configuration file in the root directory. Instructions will follow to populate these settings.

### Configuration Settings
TBD

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
