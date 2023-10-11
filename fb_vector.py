import featurebase

fb_client = featurebase.client(
	hostport="query.featurebase.com/v2",
	database="147b0d80-ce46-4400-af0e-f63b395dc1fc",
	apikey="791ec221-ec06-4494-9fce-1f9f78e614e3"
)

# create the db
sql = "CREATE TABLE testdb (_id id, sentence string, embedding vector(768));"
fb_client.query(sql=sql)

from InstructorEmbedding import INSTRUCTOR

model = INSTRUCTOR('hkunlp/instructor-xl')
sentence = "3D ActionSLAM: wearable person tracking in multi-floor environments"
embeddings = model.encode([sentence]).tolist()

# get the single 768 element vector (list of floats)
embedding = embeddings[0] # get the first embedding

# insert into featurebase
sql = f"INSERT INTO testdb VALUES (1, '{sentence}', {embedding})"
result = fb_client.query(sql=sql)

print(result.error)