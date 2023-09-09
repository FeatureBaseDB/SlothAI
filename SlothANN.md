SlothANN

In the realm of data analysis and information retrieval, the efficient storage and comparison of vectors have long been central challenges. Enter SlothANN, a solution designed to tackle this fundamental problem using semantic knowledge graphs.

## Background
A semantic knowledge graph, often simply referred to as a knowledge graph, is a structured representation of knowledge that captures the relationships between entities and concepts in a domain. It is a graph-based data model that organizes information in a way that makes it easy to understand and query, emphasizing the semantic meaning of the data.

Semantic graphs have been implemented in a wide variety of search engines for a wide variety of use cases.

Storing large volumes of vectors while maintaining accessibility and speed is no small feat. Traditional approaches often encounter scalability issues, particularly when dealing with high-dimensional data. This challenge arises due to the inherent linearity of certain distance calculations, such as cosine distance. While accurate, exact calculation of distance can become impractical as the numbers of vectors increase.

SlothANN harnesses the power of semantic graphs and keyterm extraction techniques to solve this issue. As data is indexed, it constructs a semantic graph of vectors, enriching the intelligence and context-awareness of your search operations. This allows a system to scale non-linearly while directly linking accuracy of the results to the model used to build the semantic graph.

SlothANN is implemented at the application layer and fine-tunes the vector layout, which allows the user choice in striking a balance between efficiency and accuracy. This approach ensures that even with vast datasets, vector storage and similarity searches remain efficient.

SlothANN may be easily modified to support a wide variety of approaches to segmenting and "crawling" the vector space for relevant entries in a given datastore. Segmenting on new conditions in SQL allows the user to optimize and control the amount of time it takes to find manageable amounts of vectors for comparison.

SlothANN is designed to leverage set operations on data provided by generative models. Any datastore capable of providing rapid set operations will scale even the slowest vector similarity functions to millions of entries using this approach.

SlothANN depends on keyterm extraction for building graphs to segment the vector space. The speed of indexing is limited to the type of model used for extracting keyterms and the level of asynchronicity available to a given model.

If you would prefer to use this solution directly, head on over to https://ai.featurebase.com/ to get started.

## Implementation Requirements
We assume the system is capable of receiving text and embedding the text as a dense vector. OpenAI embeddings return vectors with 1,536 elements and open models like Instructor-Large return vectors with 768 elements.

We also assume the system is capable of extracting keyterms from the text. If you are using OpenAI endpoints, the following template may be used to return a Python dictionary (as a string) that contains the 'keyterms' key and array of keyterms as its value:

```
# complete dict task
1. Build an entry for the dictionary that has a 'text' key for the following text:
"""
$text
"""
3. Build an entry for the dictionary that has a 'keyterms' key for an array of up to (5) keyterms from the text: in step 1.
python_dict =
```

We assume the system processes text blocks of ~512 characters per entry. We choose this value because some open models have 512 as a token limit for processing, and we (naively) assume 1 token per character.

```
{
  "keyterms": ['door', 'silence', 'sudden', 'knock']
}
```

Finally, we assume the use of a datastore capable of rapid set operations on the keyterms and graph nodes, such as FeatureBase.

## Defining Outliers
An outlier refers to an observation or data point that significantly deviates from the rest of the data in a dataset. Outliers are often unusual, rare, or anomalous in some way and can have a substantial impact on statistical analysis and machine learning models if not handled properly.

In SlothANN, outliers are assumed to meet the conditions that they a) follow a leader, AND b) not have followers, OR c) the do not follow a leader or have followers. The number of the last type outliers will always be limited to the load incurred by the distance calculation function in the system.

## Implementing Leaders 
Leaders are implemented with sets and are stored in a table we create to track them:

```
CREATE TABLE leaders (leader_id _id, outlier boolean, follows stringset, followers stringset)
```

We initialize a leader with an id and whether or not the leader is currently an outlier. If the leader is NOT an outlier, we assume that the leader either has followers, or that it follows another leader.

## Entry Processing
When a new record arrives, we initially consider it an outlier and move to insert it into the datastore. There is only one thing that will stop us from doing this, and that is load on the system:

```
SELECT 




Search leaders:
SELECT text, field_1, cosine_distance(SELECT text, embedding FROM usertable WHERE graph = 'leaders_at5z', embedding) AS distance FROM usertable ORDER BY distance ASC);
Pseudo code to rebalance:
if execution_time > 500ms:
    SELECT text, tanimoto_similarty(SELECT text, keyterms FROM usertable WHERE graph = 'leaders_1'