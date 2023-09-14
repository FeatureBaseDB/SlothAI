#!/bin/bash
#curl -X POST https://ai.featurebase.com/tasks/process/753bs0842ec109/8qr64iVd4WNp3KDoF -d '{

curl -X POST 127.0.0.1:8080/tasks/process/753bs0842ec109/tfLgaeA7WHiXISNWQ -d '{
  "models": {
  },
  "name": "slothy",
  "openai_token": "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",
  "tid": "uLIo3Ucwrxw2w9h4m",
  "uid": "tfLgaeA7WHiXISNWQ",
  "schema": null,
  "data": {
    "text": ["the edge of poohs nose nudged the honey pot and it suddenly tumbled from the table."],
    "keyterms": [["steve", "max"],["ralph", "jack"]],
    "vector": [[0.33,0.22],[0.2,0.1]],
    "other_set": ["bob", "steve"]
  }
}'
