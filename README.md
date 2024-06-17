# Book-Recommendation-System
Contains the Files necessary to run the book recommendation system

## Required Procedure:
To install all the libraries run the following windows command:

```bash
pip install flask pymongo numpy
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

To call the Stalls API, you can use the following command:
```bash
curl -X GET http://127.0.0.1:5000/stalls/52207
```



