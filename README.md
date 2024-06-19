# Book-Recommendation-System
Contains the Files necessary to run the book recommendation system

## Required Procedure:
first and foremost, to use this API, clone the data from this API using this command in the cmd:
```bash
git clone https://github.com/Deepanshu-mehlawat/Book-Recommendation-System.git
```

To install all the libraries run the following windows command:

```bash
pip install flask pymongo numpy nltk tensorflow
```
Now we need to download the 'punkt' data for NLTK to work.
follow the following steps to download 'punkt':

1)open command prompt.

2)start python by typing 'python':
```bash
python
```
3)now that you started python, start by importing nltk.
```python
import nltk
```
4)Now run the following code next:
```python
nltk.download('punkt')
nltk.download('wordnet')
```
5) thats it, you can type 'exit()' to exit python and proceed with further steps.


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




