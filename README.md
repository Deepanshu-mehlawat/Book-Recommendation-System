# Book-Recommendation-System
Contains the Files necessary to run the book recommendation system

## Required Procedure:
first and foremost, to use this API, clone the data from this API using this command in the cmd:
```bash
git clone https://github.com/Deepanshu-mehlawat/Book-Recommendation-System.git
```

To install all the libraries run the following windows command:

```bash
pip install -r requirements.txt
```
Now we need to download the 'punkt' and 'wordnet' data for NLTK to work.
follow the following steps to download it:

1)open command prompt.

2)Just run the followingcommand and wait till its finished running:
```bash
python nltk_setup.py
```

To run the Flask API, you can run the following command in your command prompt:
```bash
python API.py
```

## Calling the APIs:
To call search API, you can use the following command:
```bash
curl -X POST -H "Content-Type: application/json" -d "{\"search_term\":\"search_term\"}" http://127.0.0.1:5000/search
```

To call Chatbot API, you can use the following command:
```bash
curl -X POST http://127.0.0.1:5000/chat -H "Content-Type: application/json" -d "{\"message\": \"[search_term]\"}"
```

To call the Stalls API, you can use the following command:
```bash
curl -X GET http://127.0.0.1:5000/stalls/52207
```

To call the top authors API, you can use the following command:
```bash
curl http://localhost:5000/top_authors
```

To call the recommendations API, you can use the following command:
```bash
curl "http://127.0.0.1:5000/top_clicks?user_id=6687beec63c6aa340358ed43"
```




