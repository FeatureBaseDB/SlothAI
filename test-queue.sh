#!/bin/bash
#curl -X POST https://ai.featurebase.com/tasks/process/753bs0842ec109/8qr64iVd4WNp3KDoF -d '{

curl -X POST 127.0.0.1:8080/tasks/process/753bs0842ec109/tfLgaeA7WHiXISNWQ -d '{
  "models": {
    "embedding": "instructor-large",
    "keyterms": "gpt-4"
  },
  "name": "slothy",
  "openai_token": "sk-BLAT",
  "tid": "DfMDtaGl0exQTiGoR",
  "uid": "tfLgaeA7WHiXISNWQ",
  "schema": null,
  "data": {
    "text": ["the edge of poohs nose nudged the honey pot and it suddenly tumbled from the table."]
  }
}'
