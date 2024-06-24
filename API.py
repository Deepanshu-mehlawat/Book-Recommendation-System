from flask import Flask, jsonify, request, render_template
import pymongo
import random
import chatbot
from difflib import SequenceMatcher
import numpy as np

app = Flask(__name__)

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["Books_db"]
books_collection = db["Books"]
stalls_collection = db['Stalls']

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/stalls/<int:book_id>', methods=['GET'])
def stalls_by_book(book_id):
    # Find stalls related to the given book_id
    stalls = list(stalls_collection.find({'bookID': book_id}, {'_id': 0, 'stall_id': 1, 'IsAuthor': 1, 'stall_impressions': 1}))

    # Sort stalls by isAuthor (True first) and then by stall_impressions (descending)
    sorted_stalls = sorted(stalls, key=lambda x: (not x['IsAuthor'], -x['stall_impressions']))

    # Prepare JSON response with stall_id and rec flag (1 for isAuthor, 0 otherwise)
    response = [{'stall_id': stall['stall_id'], 'rec': 1 if stall['IsAuthor'] else 0} for stall in sorted_stalls]

    return jsonify({'stalls': response})

@app.route('/top_clicks', methods=['GET'])
def top_clicks():
    top_books = list(books_collection.find({}, {'_id': 0, 'id': 1, 'clicks': 1}).sort([('clicks', -1)]).limit(5))
    top_book_ids = [book['id'] for book in top_books]
    return jsonify({'top_books_by_clicks': top_book_ids})

@app.route('/top_impressions', methods=['GET'])
def top_impressions():
    top_books = list(books_collection.find({}, {'_id': 0, 'id': 1, 'impressions': 1}).sort([('impressions', -1)]).limit(5))
    top_book_ids = [book['id'] for book in top_books]
    return jsonify({'top_books_by_impressions': top_book_ids})

def calculate_similarity(search_term, text):
    matcher = SequenceMatcher(None, search_term.lower(), text.lower())
    return matcher.ratio()

@app.route('/search', methods=['GET', 'POST'])
def search_books():
    search_term = ''
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'search_term' not in data:
            return jsonify({'error': 'Missing search term in request data'}), 400
        search_term = data['search_term']
    else:  # GET request
        search_term = request.args.get('search_term')
        if not search_term:
            return jsonify({'error': 'Missing search term in request data'}), 400

    # Exact match search in title
    title_matches = list(books_collection.find(
        {'Title': {'$regex': search_term, '$options': 'i'}},
        {'_id': 0, 'id': 1, 'Title': 1, 'Authors': 1, 'Category': 1, 'clicks': 1}
    ).sort('clicks', -1))

    # Exact match search in authors
    author_matches = list(books_collection.find(
        {'Authors': {'$regex': search_term, '$options': 'i'}},
        {'_id': 0, 'id': 1, 'Title': 1, 'Authors': 1, 'Category': 1, 'clicks': 1}
    ).sort('clicks', -1))

    # Exact match search in category
    category_matches = list(books_collection.find(
        {'Category': {'$regex': search_term, '$options': 'i'}},
        {'_id': 0, 'id': 1, 'Title': 1, 'Authors': 1, 'Category': 1, 'clicks': 1}
    ).sort('clicks', -1))

    # Combine exact matches in the specified order without duplicates
    exact_matches = title_matches + \
                    [match for match in author_matches if match not in title_matches] + \
                    [match for match in category_matches if match not in title_matches and match not in author_matches]

    if len(exact_matches) >= 5:
        return jsonify({'books': exact_matches[:5]})

    # If fewer than 5 exact matches, find similar books
    all_books = list(books_collection.find({}, {'_id': 0, 'id': 1, 'Title': 1, 'Authors': 1, 'Category': 1, 'clicks': 1}))
    similarity_scores = [
        (
            max(
                calculate_similarity(search_term, book['Title']),
                calculate_similarity(search_term, book['Authors']),
                calculate_similarity(search_term, book['Category'])
            ),
            book
        )
        for book in all_books
    ]

    # Sort by similarity score in descending order
    similarity_scores.sort(key=lambda x: x[0], reverse=True)

    # Combine exact matches with the top similar books, ensuring no duplicates
    combined_results = exact_matches + [score[1] for score in similarity_scores if score[1] not in exact_matches]

    return jsonify({'books': combined_results[:5]})



WORDS_TO_REMOVE = {"search", "find", "book","books","by","on", "available","want","fair","bookfair"}

def clean_message(message):
    words = message.split()
    cleaned_words = [word for word in words if word.lower() not in WORDS_TO_REMOVE]
    return ' '.join(cleaned_words)

@app.route('/chat', methods=['POST'])
def chat():
  if request.method == 'POST':
    data = request.get_json()
    if not data or 'message' not in data:
      return jsonify({'error': 'Missing message in request data'}), 400
    user_message = data['message'].lower()

    # Call methods from chatbot.py to process the message
    intents = chatbot.predict_class(user_message)
    response = chatbot.get_response(intents, chatbot.intents)
    if response == 'Searching':
        # Get the top 5 books based on the search string (user message)
        cleaned_message = clean_message(user_message)
        top_books = get_top_books(cleaned_message)
        return jsonify({'response': response, 'action': 2, 'data': top_books})
    elif response == 'booking':
        return jsonify({'response': response,'action':1})
    return jsonify({'response': response,'action':0})
  else:
    return jsonify({'error': 'Invalid request method'}), 405

def fetch_all_books():
    return list(books_collection.find({}, {"id": 1, "Title": 1, "Authors": 1, "Category": 1}))

def calculate_similarity1(search_string, book_data):
    similarity_scores = []
    for book in book_data:
        combined_text = f"{book['Title'].lower()} {book['Authors'].lower()} {book['Category'].lower()}"
        similarity = SequenceMatcher(None, search_string.lower(), combined_text).ratio()
        similarity_scores.append(similarity)
    return similarity_scores

def get_top_books(search_string):
    # Fetch all books from the database
    books = fetch_all_books()

    # First look for exact matches in the title
    exact_matches = []
    for book in books:
        if book['Title'].lower() in search_string.lower():
            exact_matches.append(book)

    # If fewer than 5 exact matches, look for exact matches in the authors
    if len(exact_matches) < 5:
        for book in books:
            if book['Authors'].lower() in search_string.lower() and book not in exact_matches:
                exact_matches.append(book)

    # If fewer than 5 exact matches, look for exact matches in the category
    if len(exact_matches) < 5:
        for book in books:
            if book['Category'].lower() in search_string.lower() and book not in exact_matches:
                exact_matches.append(book)

    # If fewer than 5 exact matches, apply similarity search for the remaining slots
    if len(exact_matches) < 5:
        similarity_scores = calculate_similarity1(search_string, books)
        scored_books = list(zip(books, similarity_scores))
        scored_books.sort(key=lambda x: x[1], reverse=True)

        for book, score in scored_books:
            if book not in exact_matches:
                exact_matches.append(book)
            if len(exact_matches) == 5:
                break

    # Prepare the top 5 unique book details
    top_books = []
    seen_books = set()
    for book in exact_matches:
        if book['id'] not in seen_books:
            book_details = {
                "id": book['id'],
                "title": book['Title'],
                "authors": book['Authors'],
                "category": book['Category']
            }
            top_books.append(book_details)
            seen_books.add(book['id'])
        if len(top_books) == 5:
            break

    return top_books

def get_top_authors():
    # Aggregation pipeline to find top 5 authors based on clicks
    pipeline = [
        {"$group": {"_id": "$Authors", "total_clicks": {"$sum": "$clicks"}}},
        {"$sort": {"total_clicks": -1}},
        {"$limit": 5}
    ]
    return list(books_collection.aggregate(pipeline))

def get_random_book_id_by_author(author):
    books = list(books_collection.find({"Authors": author}, {"id": 1}))
    if books:
        book = random.choice(books)
        if book:
            return str(book["id"])  # Convert ObjectId to string
    return None

@app.route('/top_authors', methods=['GET'])
def suggest_books():
    top_authors = get_top_authors()
    suggestions = []

    for author in top_authors:
        book_id = get_random_book_id_by_author(author['_id'])  # Use '_id' here
        if book_id:
            suggestions.append(book_id)
    
    return jsonify(suggestions)


if __name__ == '__main__':
    app.run(debug=True)
